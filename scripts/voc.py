"""Command line for the VoC copilot pipeline.

Run from the project root with:  python3 -I scripts/voc.py <command> ...
Commands: ingest, gate-eval, baseline, extract, eval
"""
import argparse
import csv
import datetime
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from voc import baselines, extract, gate, ingest, metrics  # noqa: E402
from voc.validate import validate_files  # noqa: E402

GOLDEN = "data/golden"


def read_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def fmt(x):
    return "n/a" if x is None else "%.3f" % x


def cmd_ingest(a):
    n = ingest.ingest(a.raw, a.db)
    print("ingested", n, "reviews into", a.db)
    print("gate:", gate.apply_gate(a.db))


def cmd_gate_eval(a):
    inputs = read_jsonl("%s/%s_for_ai.jsonl" % (GOLDEN, a.split))
    gold = {l["reviewId"]: l for l in read_jsonl(a.gold or "%s/labels_ai/%s_ai_labels.jsonl" % (GOLDEN, a.split))}
    passed = fn = act = 0
    misses = []
    for r in inputs:
        d, _ = gate.gate(r["content"], r["score"])
        passed += d == "pass"
        g = gold.get(r["reviewId"])
        if g and metrics.actionable(g):
            act += 1
            if d == "skip":
                fn += 1
                misses.append(r["content"][:80])
    print("reviews %d | gate pass rate %.1f%%" % (len(inputs), 100 * passed / len(inputs)))
    print("actionable (gold) %d | false negatives %d | FN rate %s (bar: <= 0.020)" %
          (act, fn, fmt(fn / act if act else None)))
    for m in misses[:10]:
        print("  missed:", m)


def cmd_baseline(a):
    fn = baselines.KINDS[a.kind]
    inputs = read_jsonl(a.input)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "labels.jsonl"), "w") as f:
        for r in inputs:
            f.write(json.dumps(fn(r), ensure_ascii=False) + "\n")
    n, nl, errs = validate_files(a.input, os.path.join(a.out, "labels.jsonl"))
    print("baseline %s wrote %d labels, validation errors: %d" % (a.kind, nl, len(errs)))


GROQ_FREE_TPD = 200000  # tokens per day for gpt-oss on Groq's free tier, per docs; UNCONFIRMED


def cmd_extract(a):
    import math
    from voc.env import load_dotenv
    from voc.llm import LLM, provider_of
    load_dotenv(str(ROOT / ".env"))
    models = a.model.split(",")
    providers = {provider_of(m) for m in models}
    if not a.dry_run:
        for prov, var in (("anthropic", "ANTHROPIC_API_KEY"), ("groq", "GROQ_API_KEY")):
            if prov in providers and not os.environ.get(var):
                sys.exit("%s not found. Put it in .env (see README) or export it." % var)
    inputs = read_jsonl(a.input)
    if a.limit:
        inputs = inputs[:a.limit]
    # flags mode has a longer prompt and answer, so Groq's 8,000 tokens a minute fits fewer reviews per call
    batch = a.batch_size or ((6 if a.mode == "flags" else 10) if provider_of(models[0]) == "groq" else 1)
    system = extract.build_system(str(ROOT), mode=a.mode)
    system_batch = extract.build_system(str(ROOT), batch=True, mode=a.mode)
    if a.dry_run:
        sys_tok = len(system_batch if batch > 1 else system) / 4  # rough: 4 characters per token
        rev_tok = sum(len(extract.user_message(r)) for r in inputs) / 4
        calls = math.ceil(len(inputs) / batch)
        est_in = calls * sys_tok + rev_tok
        est_out = len(inputs) * 200
        print("DRY RUN (no API call made): %d reviews | models %s | batch size %d" % (len(inputs), models, batch))
        print("estimated calls %d | input tokens ~%d | output tokens ~%d (rough, excludes reasoning tokens)" %
              (calls, est_in, est_out))
        if provider_of(models[0]) == "groq":
            print("vs Groq free daily token cap %d (unconfirmed): ~%d%% used" %
                  (GROQ_FREE_TPD, round(100 * (est_in + est_out) / GROQ_FREE_TPD)))
        print("first user message:", extract.user_message(inputs[0]))
        return
    meta = extract.run_extraction(inputs, LLM(a.cache_db, wait_on_daily=not a.stop_on_daily_limit), system, models, a.effort, a.workers, a.out,
                                  batch_size=batch, system_batch=system_batch, mode=a.mode)
    print(json.dumps(meta, indent=2))


def cmd_eval(a):
    if a.split == "test":
        if not a.final:
            sys.exit("Test split is touched once per release candidate. Re-run with --final to confirm.")
        os.makedirs("evals", exist_ok=True)
        with open("evals/test_runs.log", "a") as f:
            f.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), a.pred))
    inputs = read_jsonl("%s/%s_for_ai.jsonl" % (GOLDEN, a.split))
    gold = {l["reviewId"]: l for l in read_jsonl(a.gold or "%s/labels_ai/%s_ai_labels.jsonl" % (GOLDEN, a.split))}
    pred = {l["reviewId"]: l for l in read_jsonl(a.pred)}
    text = {r["reviewId"]: r["content"] for r in inputs}
    ids = [r["reviewId"] for r in inputs if r["reviewId"] in gold]
    strata = {}
    if os.path.exists("%s/manifest.csv" % GOLDEN):
        strata = {r["reviewId"]: r["stratum"] for r in csv.DictReader(open("%s/manifest.csv" % GOLDEN))}
    print("NOTE: gold = AI labels (not human-verified). n=%d, missing predictions: %d" %
          (len(ids), sum(1 for i in ids if i not in pred)))

    def show(name, ids_):
        m = metrics.evaluate(gold, pred, ids_)
        print("\n== %s (n=%d) ==" % (name, m["n"]))
        print("usable   P %s R %s" % (fmt(m["usable"]["precision"]), fmt(m["usable"]["recall"])))
        print("aspect   P %s R %s F1 %s" % (fmt(m["aspect"]["precision"]), fmt(m["aspect"]["recall"]), fmt(m["aspect"]["f1"])))
        print("review-level category F1 %s | category macro-F1 %s" %
              (fmt(m["review_level_category"]["f1"]), fmt(m["category_macro_f1"])))
        print("sentiment kappa %s | severity weighted kappa %s | critical recall %s (gold n=%d)" %
              (fmt(m["sentiment_kappa"]), fmt(m["severity_weighted_kappa"]), fmt(m["critical_recall"]), m["critical_gold_n"]))
        return m

    show("ALL", ids)
    groups = {"stratum": strata.get, "script": lambda i: ingest.lang_script(text[i]),
              "length": lambda i: metrics.length_bucket(text[i])}
    for gname, fn in groups.items():
        for val in sorted({fn(i) for i in ids if fn(i)}):
            sub = [i for i in ids if fn(i) == val]
            if len(sub) >= 10:
                show("%s=%s" % (gname, val), sub)


def cmd_analyze(a):
    from voc import aggregate, regress, themes
    inputs = read_jsonl(a.reviews)
    labels = {l["reviewId"]: l for l in read_jsonl(a.labels)}
    reviews = [{"review_id": r["reviewId"], "date": r["date"], "score": r["score"],
                "version": r.get("appVersion") or "unknown"} for r in inputs if r["reviewId"] in labels]
    aspects = []
    for rid, lab in labels.items():
        for x in lab["aspects"]:
            if x["category"] in ("praise", "other"):
                continue
            if x["sentiment"] in ("negative", "mixed") or x["category"] == "feature_request":
                aspects.append({"review_id": rid, "category": x["category"], "aspect": x["aspect"],
                                "sentiment": x["sentiment"], "severity": x["severity"]})
    tlist = themes.build_themes(aspects, a.threshold, a.min_size)
    if a.merge_model:
        from voc import theme_merge
        from voc.env import load_dotenv
        from voc.llm import LLM
        load_dotenv(str(ROOT / ".env"))
        before = (sum(1 for t in tlist if t["status"] == "ranked"), len(tlist), theme_merge.coverage(aspects, tlist))
        tlist, mrep = theme_merge.merge_all(LLM(a.cache_db), a.merge_model, aspects, tlist, a.min_size)
        after = (sum(1 for t in tlist if t["status"] == "ranked"), len(tlist), theme_merge.coverage(aspects, tlist))
        print("AI merge (%s): themes %d -> %d | ranked %d -> %d | share of problem reviews in a ranked theme %.0f%% -> %.0f%%" %
              (a.merge_model, before[1], after[1], before[0], after[0], 100 * before[2], 100 * after[2]))
        print("  model dropped %d unknown ids, forgot %d groups (kept alone)\n" %
              (sum(r.get("dropped_unknown_ids", 0) for r in mrep.values()),
               sum(r.get("forgotten_kept_alone", 0) for r in mrep.values())))
    dates = sorted(r["date"] for r in reviews)
    start, end = a.start or dates[0], a.end or dates[-1]
    ranked = aggregate.rank_themes(reviews, aspects, tlist, start, end, a.prev_start or "", a.prev_end or "")
    print("reviews %d (%s to %s) | problem aspects %d | themes %d (ranked %d, emerging %d)" %
          (len(reviews), start, end, len(aspects), len(tlist),
           sum(1 for t in tlist if t["status"] == "ranked"), sum(1 for t in tlist if t["status"] == "emerging")))
    if not a.prev_start:
        print("note: no previous window given, so trend is neutral (1.0) for every theme")
    print("\nTOP THEMES BY PRIORITY (priority = severity score x trend; drag = rating lift if fixed)")
    for t in [x for x in ranked if x["status"] == "ranked"][:a.top]:
        print("%7.1f  %2d reviews (%4.1f%%)  drag %.3f  %-24s %s" %
              (t["priority"], t["reviews"], 100 * t["share"], t["rating_drag"], t["category"], t["name"]))
    print("\nEMERGING (fewer than %d reviews, low evidence): %d themes" %
          (a.min_size, sum(1 for x in ranked if x["status"] == "emerging")))
    res = regress.compare(reviews, aspects)
    enough = [r for r in res if min(r["n_base"], r["n_new"]) >= regress.MIN_N and r["subject"] == "negative_share"]
    flagged = [r for r in res if r["flag"]]
    print("\nRELEASE REGRESSION: %d version pairs compared, %d with enough reviews (n >= %d), %d flagged" %
          (len({(r["baseline"], r["version"]) for r in res}), len(enough), regress.MIN_N, len(flagged)))
    for r in flagged:
        print("  FLAG %s -> %s: %s %.0f%% -> %.0f%% (adjusted p %.4f)" %
              (r["baseline"], r["version"], r["subject"], 100 * r["share_base"], 100 * r["share_new"], r["p_adj"]))
    ub = regress.unknown_bucket(reviews)
    print("unknown-version bucket: %d reviews, negative share %s" %
          (ub["n"], "n/a" if ub["negative_share"] is None else "%.0f%%" % (100 * ub["negative_share"])))
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "analysis.json"), "w") as f:
            json.dump({"themes": tlist, "ranking": ranked, "regression": res}, f, indent=1, ensure_ascii=False)
        with open(os.path.join(a.out, "themes_report.md"), "w") as f:
            f.write("# Ranked themes (check each: do the example phrases describe one problem?)\n\n")
            for t in sorted([x for x in tlist if x["status"] == "ranked"], key=lambda x: -x["review_count"]):
                f.write("## %s: %s (%d reviews, merged from %d groups)\n" %
                        (t["category"], t["name"], t["review_count"], t.get("merged_from", 1)))
                for s in t["samples"]:
                    f.write("- %s\n" % s)
                f.write("\n")
        print("\nsaved", os.path.join(a.out, "analysis.json"), "and themes_report.md")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("ingest"); s.add_argument("raw"); s.add_argument("--db", default="data/app.db"); s.set_defaults(f=cmd_ingest)
    s = sp.add_parser("gate-eval"); s.add_argument("--split", default="dev"); s.add_argument("--gold"); s.set_defaults(f=cmd_gate_eval)
    s = sp.add_parser("baseline"); s.add_argument("--kind", choices=list(baselines.KINDS), required=True)
    s.add_argument("--input", required=True); s.add_argument("--out", required=True); s.set_defaults(f=cmd_baseline)
    s = sp.add_parser("extract"); s.add_argument("--input", required=True); s.add_argument("--out", required=True)
    s.add_argument("--model", default="openai/gpt-oss-120b", help="primary,escalation,... (comma separated)")
    s.add_argument("--mode", choices=["flags", "direct"], default="flags",
                   help="flags: model reports impact facts, code derives severity; direct: model gives severity")
    s.add_argument("--effort", default="low", help="reasoning effort (Groq gpt-oss and Claude)")
    s.add_argument("--workers", type=int, default=1, help="keep at 1 on Groq's free tier")
    s.add_argument("--batch-size", type=int, default=0, help="reviews per call; 0 = 10 for Groq, 1 for Claude")
    s.add_argument("--limit", type=int); s.add_argument("--dry-run", action="store_true")
    s.add_argument("--stop-on-daily-limit", action="store_true",
                   help="stop cleanly when the daily token limit is hit; rerun later to resume (answers are cached)")
    s.add_argument("--cache-db", default="data/llm_cache.db"); s.set_defaults(f=cmd_extract)
    s = sp.add_parser("analyze"); s.add_argument("--reviews", required=True); s.add_argument("--labels", required=True)
    s.add_argument("--start"); s.add_argument("--end"); s.add_argument("--prev-start"); s.add_argument("--prev-end")
    s.add_argument("--threshold", type=float, default=0.2); s.add_argument("--min-size", type=int, default=5)
    s.add_argument("--top", type=int, default=12); s.add_argument("--out")
    s.add_argument("--merge-model", help="optional AI step that merges groups meaning the same problem, e.g. openai/gpt-oss-20b")
    s.add_argument("--cache-db", default="data/llm_cache.db"); s.set_defaults(f=cmd_analyze)
    s = sp.add_parser("eval"); s.add_argument("--split", choices=["dev", "test"], default="dev")
    s.add_argument("--pred", required=True); s.add_argument("--gold"); s.add_argument("--final", action="store_true")
    s.set_defaults(f=cmd_eval)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
