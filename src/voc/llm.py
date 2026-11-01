"""Single wrapper for model calls: content-hash cache, refusal handling, usage and cost logging.

Providers: Anthropic (model ids starting with "claude-") and Groq (everything else).
Rules (docs/system_spec.md section 5): pinned model IDs, no sampling parameters (rejected by the
Anthropic API from 2026-10-21), structured output instead of forced tool choice.
The Groq adapter follows Groq's published request shape but has not been run against the live API yet.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# USD per million tokens (input, output, cache_read), from the API reference cached 2026-10-06.
# Haiku cache-read price is assumed at 0.1x input. Costs are estimates, not billing.
# Models missing from this table (e.g. Groq free tier) cost 0.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
}

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_STRICT_MODELS = ("openai/gpt-oss-",)  # strict json_schema per Groq docs (also two preview models)

CACHE_DDL = """CREATE TABLE IF NOT EXISTS llm_cache (
  key TEXT PRIMARY KEY, model TEXT, text TEXT, usage_json TEXT, created_at REAL)"""


class ProviderError(Exception):
    """A provider call failed in a way retrying will not fix (message never contains secrets)."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status, self.code = status, code


@dataclass
class Result:
    text: str = ""
    model: str = ""
    refused: bool = False
    refusal_category: str = ""
    stop_reason: str = ""
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_s: float = 0.0
    cached: bool = False
    request_id: str = ""


def provider_of(model: str) -> str:
    return "anthropic" if model.startswith("claude-") else "groq"


def estimate_cost(model: str, usage: dict) -> float:
    p_in, p_out, p_cr = PRICES.get(model, (0.0, 0.0, 0.0))
    fresh = usage.get("input_tokens", 0)
    write = usage.get("cache_creation_input_tokens", 0)
    read = usage.get("cache_read_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    return (fresh * p_in + write * p_in * 1.25 + read * p_cr + out * p_out) / 1e6


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def http_post(url: str, headers: dict, body: dict, timeout: int = 120):
    """Return (status, headers, parsed_json). Never raises on HTTP error statuses."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw[:300]}
        return e.code, dict(e.headers), data


class LLM:
    def __init__(self, cache_db: str = "data/llm_cache.db", client=None, groq_post=None, sleep=time.sleep,
                 wait_on_daily: bool = True):
        self.cache_db = cache_db
        self._client = client
        self._groq_post = groq_post
        self._sleep = sleep
        self.wait_on_daily = wait_on_daily  # False: raise at once on a daily token limit instead of waiting
        conn = sqlite3.connect(cache_db)
        conn.execute(CACHE_DDL)
        conn.commit()
        conn.close()

    # ---- cache -------------------------------------------------------------------------
    @staticmethod
    def key(model, effort, system, user, schema) -> str:
        blob = json.dumps([model, effort, system, user, schema], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def _cache_get(self, k):
        conn = sqlite3.connect(self.cache_db, timeout=30)
        row = conn.execute("SELECT text, usage_json FROM llm_cache WHERE key=?", (k,)).fetchone()
        conn.close()
        return row

    def _cache_put(self, k, model, text, usage):
        conn = sqlite3.connect(self.cache_db, timeout=30)
        conn.execute("INSERT OR REPLACE INTO llm_cache VALUES (?,?,?,?,?)",
                     (k, model, text, json.dumps(usage), time.time()))
        conn.commit()
        conn.close()

    # ---- public ------------------------------------------------------------------------
    def call(self, *, model: str, system: str, user: str, schema: dict, effort: str,
             max_tokens: int = 4000) -> Result:
        k = self.key(model, effort, system, user, schema)
        row = self._cache_get(k)
        if row:
            return Result(text=row[0], model=model, usage=json.loads(row[1]), cached=True)
        if provider_of(model) == "anthropic":
            res, cacheable = self._call_anthropic(model, system, user, schema, effort, max_tokens)
        else:
            res, cacheable = self._call_groq(model, system, user, schema, max_tokens, effort)
        if cacheable:
            self._cache_put(k, model, res.text, res.usage)
        self._log_call(model, res)
        return res

    def _log_call(self, model: str, res: Result) -> None:
        """Append one line per real (not cached) call: time and tokens, for the latency and cost reports."""
        try:
            with open(self.cache_db + ".calls.jsonl", "a") as f:
                f.write(json.dumps({"ts": round(time.time(), 1), "model": model, "latency_s": round(res.latency_s, 3),
                                    "input_tokens": res.usage.get("input_tokens", 0),
                                    "output_tokens": res.usage.get("output_tokens", 0),
                                    "refused": res.refused, "stop": res.stop_reason}) + "\n")
        except OSError:
            pass

    # ---- Anthropic ---------------------------------------------------------------------
    def client(self):
        if self._client is None:
            import anthropic  # needs Python 3.10+ and a configured API key
            self._client = anthropic.Anthropic()
        return self._client

    def _call_anthropic(self, model, system, user, schema, effort, max_tokens):
        t0 = time.time()
        resp = self.client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        )
        u = resp.usage
        usage = {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        }
        res = Result(model=model, stop_reason=resp.stop_reason or "", usage=usage,
                     cost_usd=estimate_cost(model, usage), latency_s=time.time() - t0,
                     request_id=getattr(resp, "_request_id", "") or "")
        if resp.stop_reason == "refusal":
            res.refused = True
            sd = getattr(resp, "stop_details", None)
            res.refusal_category = (getattr(sd, "category", None) or "") if sd else ""
            return res, False  # never cache refusals
        res.text = next((b.text for b in resp.content if b.type == "text"), "")
        return res, bool(resp.stop_reason == "end_turn" and res.text)

    # ---- Groq (OpenAI-compatible chat completions) --------------------------------------
    def _call_groq(self, model, system, user, schema, max_tokens, effort=""):
        post = self._groq_post
        headers = {"Content-Type": "application/json", "User-Agent": "voc-copilot/0.1"}
        if post is None:
            key = os.environ.get("GROQ_API_KEY")
            if not key:
                raise ProviderError("GROQ_API_KEY not set (put it in .env)")
            headers["Authorization"] = "Bearer " + key
            post = http_post
        if model.startswith(GROQ_STRICT_MODELS):
            sys_text = system
            fmt = {"type": "json_schema",
                   "json_schema": {"name": "labels", "strict": True, "schema": schema}}
        else:  # plain JSON mode: schema goes in the prompt, validation does the rest
            sys_text = system + "\n\nReturn JSON that matches this schema exactly:\n" + json.dumps(schema)
            fmt = {"type": "json_object"}
        body = {"model": model, "response_format": fmt, "max_completion_tokens": max_tokens,
                "messages": [{"role": "system", "content": sys_text}, {"role": "user", "content": user}]}
        if model.startswith(GROQ_STRICT_MODELS) and effort in ("low", "medium", "high"):
            body["reasoning_effort"] = effort  # gpt-oss thinking tokens count against max_completion_tokens
        t0 = time.time()
        status, last_daily = 0, ""
        for attempt in range(6):
            try:
                status, hdrs, data = post(GROQ_URL, headers, body)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                status = 0  # network blip (e.g. TLS handshake timeout): back off and try again
                self._sleep(5.0 * (attempt + 1))
                continue
            if status == 200:
                break
            if status == 429 and isinstance(data, dict):
                m = re.search(r"Limit (\d+), Used (\d+), Requested (\d+)",
                              (data.get("error") or {}).get("message", "") or "")
                if m and int(m.group(3)) > int(m.group(1)):  # can never fit in one minute: do not retry
                    raise ProviderError("request (%s tokens) exceeds the per-minute limit (%s)" %
                                        (m.group(3), m.group(1)), status=429, code="request_too_large")
            if status == 429 or status >= 500:
                wait = 20.0
                try:
                    wait = float({k.lower(): v for k, v in hdrs.items()}.get("retry-after", wait))
                except (TypeError, ValueError):
                    pass
                last_msg = ((data.get("error") or {}).get("message") or "") if isinstance(data, dict) else ""
                daily = "per day" in last_msg
                if daily:
                    last_daily = last_msg
                    if not self.wait_on_daily:
                        raise ProviderError("Groq daily token limit reached: " + last_msg[:240], status=429,
                                            code="daily_limit")
                self._sleep(min(max(wait, 1.0), 1500.0 if daily else 90.0))  # daily limits free up slowly
                continue
            err = (data.get("error") or {}) if isinstance(data, dict) else {}
            msg = err.get("message")
            raise ProviderError("Groq HTTP %s: %s" % (status, (msg or str(data))[:300]),
                                status=status, code=err.get("code"))
        else:
            if last_daily:
                raise ProviderError("Groq daily token limit reached: " + last_daily[:240], status=429,
                                    code="daily_limit")
            raise ProviderError("Groq still failing after retries (%s)" %
                                ("network error" if status == 0 else "HTTP %s" % status))
        choice = data["choices"][0]
        u = data.get("usage") or {}
        usage = {"input_tokens": u.get("prompt_tokens", 0) or 0,
                 "output_tokens": u.get("completion_tokens", 0) or 0,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        text = (choice.get("message") or {}).get("content") or ""
        finish = choice.get("finish_reason") or ""
        res = Result(text=text, model=model, stop_reason=finish, usage=usage,
                     cost_usd=estimate_cost(model, usage), latency_s=time.time() - t0,
                     request_id=str(data.get("id", "")))
        return res, bool(finish == "stop" and text)  # truncated ("length") answers are never cached
