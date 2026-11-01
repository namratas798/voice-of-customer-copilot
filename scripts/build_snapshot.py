"""Build the frozen snapshot the app reads (no model call unless the theme-merge answers are not cached).

Usage: python3 -I scripts/build_snapshot.py --reviews <inputs.jsonl> --labels <labels.jsonl>
           --out app/snapshot.json [--merge-model openai/gpt-oss-20b] [--cache-db data/llm_cache.db]
"""
import argparse
import datetime
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from voc import theme_merge, themes  # noqa: E402
from voc.env import load_dotenv  # noqa: E402
from voc.llm import LLM  # noqa: E402

from voc.evidence import EVIDENCE  # noqa: E402


def read_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--merge-model", default="openai/gpt-oss-20b")
    ap.add_argument("--cache-db", default="data/llm_cache.db")
    ap.add_argument("--min-size", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=0.2)
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))

    labels = {l["reviewId"]: l for l in read_jsonl(a.labels)}
    rows = [r for r in read_jsonl(a.reviews) if r["reviewId"] in labels]
    reviews = [{"review_id": r["reviewId"], "date": r["date"], "score": r["score"],
                "version": r.get("appVersion") or "unknown", "text": r["content"]} for r in rows]
    aspects = []
    for rid, lab in labels.items():
        for x in lab["aspects"]:
            aspects.append({"review_id": rid, "category": x["category"], "aspect": x["aspect"], "sentiment": x["sentiment"],
                            "severity": x["severity"], "quote": x["quote"], "impact": x.get("impact", {}), "theme_id": None})
    problem = [x for x in aspects if x["category"] not in ("praise", "other")
               and (x["sentiment"] in ("negative", "mixed") or x["category"] == "feature_request")]
    tlist = themes.build_themes(problem, a.threshold, a.min_size)
    tlist, mrep = theme_merge.merge_all(LLM(a.cache_db), a.merge_model, problem, tlist, a.min_size)
    source = next(iter(labels.values())).get("source", "unknown")
    dates = sorted(r["date"] for r in reviews)
    snap = {
        "meta": {"snapshot_date": datetime.date.today().isoformat(), "n_reviews": len(reviews), "date_from": dates[0],
                 "date_to": dates[-1], "labeler": source, "theme_merge_model": a.merge_model,
                 "app": "Groww (Google Play, English and Hinglish)", "min_theme_size": a.min_size,
                 "sampling": "Random sample of reviews that pass the rule-based gate; golden-set and validation reviews excluded."},
        "reviews": reviews, "aspects": aspects, "themes": tlist, "evidence": EVIDENCE,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(snap, f, ensure_ascii=False)
    print("snapshot: %d reviews, %d aspects, %d themes (%d ranked) -> %s (%.0f KB)" %
          (len(reviews), len(aspects), len(tlist), sum(1 for t in tlist if t["status"] == "ranked"), a.out,
           os.path.getsize(a.out) / 1024))
    print("merge: cached=%s" % all(r.get("cached", True) for r in mrep.values() if not r.get("skipped")))


if __name__ == "__main__":
    main()
