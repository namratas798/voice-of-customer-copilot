"""Score model severity against the human's review-level ratings on a fresh validation sheet.

Usage: python3 -I scripts/score_validation.py <rated_sheet.csv> <validation_key.csv> <model_labels.jsonl>
The model's review severity is the highest severity among its aspects for that review.
"""
import collections
import csv
import json
import sys

LEVELS = ["none", "low", "medium", "high", "critical"]
sheet = {r["row"]: r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8-sig"))}
key = {r["row"]: r for r in csv.DictReader(open(sys.argv[2], encoding="utf-8-sig"))}
model = {json.loads(l)["reviewId"]: json.loads(l) for l in open(sys.argv[3]) if l.strip()}

rated = []
for row, k in key.items():
    human = sheet[row]["your_severity"].strip().lower()
    if human not in LEVELS:
        sys.exit("row %s: unrecognised severity %r (use %s)" % (row, human, ", ".join(LEVELS)))
    aspects = model.get(k["review_id"], {}).get("aspects", [])
    top = max((a["severity"] for a in aspects), key=LEVELS.index) if aspects else "none"
    rated.append((row, human, top))

hc = [r for r in rated if r[1] == "critical"]
mc = [r for r in rated if r[2] == "critical"]
tp = sum(1 for r in hc if r[2] == "critical")
exact = sum(1 for r in rated if r[1] == r[2])
near = sum(1 for r in rated if abs(LEVELS.index(r[1]) - LEVELS.index(r[2])) <= 1)
print("rated %d | your counts: %s" % (len(rated), dict(collections.Counter(r[1] for r in rated))))
print("critical: you %d, model %d, both %d | recall %.0f%% | precision %.0f%%" %
      (len(hc), len(mc), tp, 100 * tp / max(1, len(hc)), 100 * tp / max(1, len(mc))))
print("exact agreement %.0f%% | within one level %.0f%%" % (100 * exact / len(rated), 100 * near / len(rated)))
print("%-9s" % "you\\model" + "".join("%9s" % l for l in LEVELS))
for h in LEVELS:
    print("%-9s" % h + "".join("%9d" % sum(1 for r in rated if r[1] == h and r[2] == m) for m in LEVELS))
