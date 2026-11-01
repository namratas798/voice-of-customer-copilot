"""Per-review extraction with validation, one retry with the error fed back, then escalation.

Batch mode sends several reviews in one call so the long labeling guide is paid for once. Each
label is still validated on its own, and any review that fails goes back through the single path.

Modes:
  direct  the model outputs severity itself (prompt extract_v2)
  flags   the model outputs observable impact flags and code derives severity (prompt extract_v3)
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

from . import rejections, severity
from .llm import LLM, ProviderError, provider_of
from .schema import EXTRACTION_SCHEMA, FLAGS_EXTRACTION_SCHEMA
from .validate import check_label

PROMPTS = {"direct": "extract_v2", "flags": "extract_v4"}  # prompts/<name>.md, both use guide v1.1
PROMPT_VERSION = PROMPTS["direct"]  # kept for older callers

BATCH_ADDENDUM = """

--- BATCH MODE ---
You will receive a JSON array of reviews, each with reviewId, content and score.
Label every review independently. Return {"labels": [...]} with exactly one label per
review, in the same order, each carrying its own reviewId. Never let one review's text
influence the labels of another."""


def schema_for(mode: str) -> dict:
    return FLAGS_EXTRACTION_SCHEMA if mode == "flags" else EXTRACTION_SCHEMA


def batch_schema_for(mode: str) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["labels"],
            "properties": {"labels": {"type": "array", "items": schema_for(mode)}}}


def build_system(root: str = ".", batch: bool = False, mode: str = "direct") -> str:
    wrapper = open(os.path.join(root, "prompts", PROMPTS[mode] + ".md")).read()
    guide_path = os.path.join(root, "docs", "labeling_guide.md")
    if not os.path.exists(guide_path):  # a public checkout ships only the copy with invented examples
        guide_path = os.path.join(root, "docs", "labeling_guide_public.md")
    guide = open(guide_path).read()
    text = wrapper.replace("{GUIDE}", guide)
    return text + BATCH_ADDENDUM if batch else text


def user_message(review: dict) -> str:
    return json.dumps({"reviewId": review["reviewId"], "content": review["content"],
                       "score": review["score"]}, ensure_ascii=False, sort_keys=True)


def max_tokens_for(model: str, n: int, mode: str = "direct") -> int:
    """Room for the answer. Claude defaults leave room for thinking; Groq limits are tight."""
    if provider_of(model) == "anthropic":
        return 4000
    # gpt-oss thinking tokens count toward this cap (measured: ~600 per review); flags add output
    base, per = (2000, 300) if mode == "flags" else (1500, 250)
    return min(4500, base + per * (n - 1)) if n > 1 else base


class DailyLimit(Exception):
    """The provider's daily allowance is used up; the run stops and can be resumed later (answers are cached)."""


GROQ_TPM = 7600  # Groq free tier counts prompt + max_completion_tokens against 8,000 tokens a minute


def budget(model: str, system: str, user: str, n: int, mode: str) -> int:
    """max_tokens for a call, shrunk so prompt + answer room fits Groq's per-minute limit."""
    mt = max_tokens_for(model, n, mode)
    if provider_of(model) == "groq":
        room = GROQ_TPM - int((len(system) + len(user)) / 3.2)  # conservative: 3.2 characters per token
        mt = max(600, min(mt, room))
    return mt


def _call(llm, **kw):
    """llm.call, but known provider limits become a normal failure (the caller falls back)."""
    try:
        return llm.call(**kw), None
    except ProviderError as e:
        if e.code == "json_validate_failed":
            return None, "provider could not produce valid JSON (likely hit the token cap)"
        if e.code == "request_too_large":
            return None, "request too large for the provider's per-minute limit"
        if e.code == "daily_limit":
            raise DailyLimit(str(e))
        raise


def _add_usage(totals, res, share=1.0):
    totals["cost_usd"] += res.cost_usd * share
    for k, v in res.usage.items():
        totals[k] = totals.get(k, 0) + v * share
    totals["calls"] += share
    totals["cached_calls"] += int(res.cached) * share
    totals["latency_s"] = totals.get("latency_s", 0.0) + res.latency_s * share


def _check(label, review, mode, max_aspect_words=8):
    """Finalize (flags mode) and validate one label. Returns (label or None, errors)."""
    if not isinstance(label, dict):
        return None, ["label is not an object"]
    try:
        if mode == "flags":
            label = severity.finalize_label(label)
    except (ValueError, KeyError, TypeError) as e:
        return None, ["bad impact flags: %s" % e]
    errs = check_label(label, review["content"], max_aspect_words)
    if label.get("reviewId") != review["reviewId"]:
        errs.append("reviewId mismatch")
    return (label if not errs else None), errs


def _check_logged(label, review, mode, events, stage, model):
    """_check, plus one log event: how many quotes were checked and why the answer was rejected, if it was."""
    n_aspects = len(label["aspects"]) if isinstance(label, dict) and isinstance(label.get("aspects"), list) else 0
    out, errs = _check(label, review, mode)
    if events is not None:
        kinds = {}
        if n_aspects:
            for a in label["aspects"]:
                q = a.get("quote") if isinstance(a, dict) else None
                if isinstance(q, str) and q and q not in review["content"]:
                    k = rejections.quote_kind(rejections.quote_similarity(q, review["content"]))
                    kinds[k] = kinds.get(k, 0) + 1
        events.append({"kind": "check", "stage": stage, "model": model, "review_id": review["reviewId"],
                       "ok": out is not None, "aspects": n_aspects,
                       "quote_errors": sum(1 for e in errs if e.startswith("quote not found")), "quote_kinds": kinds,
                       "reasons": sorted({rejections.classify_reason(e) for e in errs})})
    return out, errs


def _log_failure(events, stage, model, message, n=1):
    if events is not None:
        events.append({"kind": "failure", "stage": stage, "model": model, "n": n,
                       "reason": rejections.classify_reason(message)})


def _try(llm, model, system, user, effort, review, totals, mode="direct", events=None, stage="single"):
    """One model call, validated. Returns (label or None, error list, refused)."""
    res, failure = _call(llm, model=model, system=system, user=user, schema=schema_for(mode),
                         effort=effort, max_tokens=budget(model, system, user, 1, mode))
    if failure:
        _log_failure(events, stage, model, failure)
        return None, [failure], False
    _add_usage(totals, res)
    if res.refused:
        _log_failure(events, stage, model, "refused")
        return None, ["refused:" + res.refusal_category], True
    try:
        label = json.loads(res.text)
    except json.JSONDecodeError:
        _log_failure(events, stage, model, "invalid JSON")
        return None, ["invalid JSON"], False
    label, errs = _check_logged(label, review, mode, events, stage, model)
    return label, errs, False


def extract_review(llm, review, system, models, effort, totals=None, mode="direct", events=None):
    """models: ordered list, first is primary, rest are escalation targets."""
    totals = totals if totals is not None else {"cost_usd": 0.0, "calls": 0, "cached_calls": 0}
    user = user_message(review)
    last_errs, any_refused = [], False
    for model in models:
        label, errs, refused = _try(llm, model, system, user, effort, review, totals, mode, events, "single")
        if label is None and not refused:  # one retry with the error fed back
            retry_user = user + "\n\nYour previous answer was invalid: " + "; ".join(errs[:5]) + \
                ". Return a corrected JSON object."
            label, errs, refused = _try(llm, model, system, retry_user, effort, review, totals, mode, events, "retry")
        any_refused = any_refused or refused
        if label is not None:
            return {"status": "ok", "model": model, "label": label, "usage": totals, "errors": []}
        last_errs = errs
    refused_only = any_refused and last_errs and last_errs[0].startswith("refused")
    return {"status": "refused" if refused_only else "failed", "model": models[-1],
            "label": None, "usage": totals, "errors": last_errs}


def extract_batch(llm, reviews, system_batch, model, effort, mode="direct", events=None):
    """One call for several reviews. Returns ({reviewId: result}, [reviews that need the single path])."""
    totals = {"cost_usd": 0.0, "calls": 0, "cached_calls": 0}
    user = json.dumps([{"reviewId": r["reviewId"], "content": r["content"], "score": r["score"]}
                       for r in reviews], ensure_ascii=False, sort_keys=True)
    res, failure = _call(llm, model=model, system=system_batch, user=user, schema=batch_schema_for(mode),
                         effort=effort, max_tokens=budget(model, system_batch, user, len(reviews), mode))
    if failure:
        _log_failure(events, "batch", model, failure, len(reviews))
        return {}, list(reviews)
    _add_usage(totals, res)
    labels = {}
    if res.refused:
        _log_failure(events, "batch", model, "refused", len(reviews))
    else:
        try:
            for lab in json.loads(res.text).get("labels", []):
                labels[lab.get("reviewId")] = lab
        except (json.JSONDecodeError, AttributeError):
            labels = {}
            _log_failure(events, "batch", model, "invalid JSON", len(reviews))
    done, redo = {}, []
    share = {k: (v / len(reviews) if isinstance(v, (int, float)) else v) for k, v in totals.items()}
    answered_whole_batch_failure = res.refused or (not labels)
    for r in reviews:
        raw = labels.get(r["reviewId"])
        if raw is None and events is not None and not answered_whole_batch_failure:
            events.append({"kind": "missing", "stage": "batch", "model": model, "review_id": r["reviewId"]})
        lab, _errs = _check_logged(raw, r, mode, None, "batch", model) if raw is None else \
            _check_logged(raw, r, mode, events, "batch", model)
        if lab is not None:
            done[r["reviewId"]] = {"status": "ok", "model": model, "label": lab, "usage": dict(share),
                                   "errors": [], "batched": True}
        else:
            redo.append(r)
    return done, redo


def run_extraction(reviews, llm, system, models, effort, workers, out_dir, batch_size=1, system_batch=None,
                   mode="direct"):
    """Runs all reviews. If the provider's daily limit is hit, stops cleanly: finished reviews are kept and
    saved, the rest are marked not_run, and a rerun later resumes from the cache."""
    os.makedirs(out_dir, exist_ok=True)
    by_id, stopped, events = {}, False, []
    pending = list(reviews)
    if batch_size > 1:
        chunks = [reviews[i:i + batch_size] for i in range(0, len(reviews), batch_size)]
        pending = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(extract_batch, llm, c, system_batch, models[0], effort, mode, events) for c in chunks]
            for c, fut in zip(chunks, futs):
                try:
                    done, redo = fut.result()
                except DailyLimit:
                    stopped = True
                    continue
                by_id.update(done)
                pending.extend(redo)
    if not stopped and pending:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [(r, ex.submit(extract_review, llm, r, system, models, effort, None, mode, events)) for r in pending]
            for r, fut in futs:
                try:
                    by_id[r["reviewId"]] = fut.result()
                except DailyLimit:
                    stopped = True
    status, cost, cached, tokens_in, tokens_out, latency = {}, 0.0, 0, 0, 0, 0.0
    not_run = {"status": "not_run", "model": "", "label": None, "errors": ["daily limit reached"],
               "usage": {"cost_usd": 0.0, "calls": 0, "cached_calls": 0}}
    with open(os.path.join(out_dir, "labels.jsonl"), "w") as lab, \
            open(os.path.join(out_dir, "usage.jsonl"), "w") as use:
        for r in reviews:
            res = by_id.get(r["reviewId"], not_run)
            status[res["status"]] = status.get(res["status"], 0) + 1
            u = res["usage"]
            cost += u["cost_usd"]
            cached += u["cached_calls"]
            tokens_in += u.get("input_tokens", 0)
            tokens_out += u.get("output_tokens", 0)
            latency += u.get("latency_s", 0.0)
            if res["label"] is not None:
                lab.write(json.dumps(res["label"], ensure_ascii=False) + "\n")
            use.write(json.dumps({"reviewId": r["reviewId"], "status": res["status"], "model": res["model"],
                                  "batched": res.get("batched", False), "errors": res["errors"], **u}) + "\n")
    meta = {"prompt_version": PROMPTS[mode] + ("_batch%d" % batch_size if batch_size > 1 else ""),
            "mode": mode, "models": models, "effort": effort, "n": len(reviews), "status": status,
            "stopped_on_daily_limit": stopped,
            "single_path_retries": len(pending) if batch_size > 1 else 0,
            "tokens_in": round(tokens_in), "tokens_out": round(tokens_out),
            "est_cost_usd": round(cost, 4), "cached_calls": round(cached),
            "model_seconds_total": round(latency, 1), "rejections": rejections.summarize(events)}
    with open(os.path.join(out_dir, "rejections.jsonl"), "w") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "run.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta
