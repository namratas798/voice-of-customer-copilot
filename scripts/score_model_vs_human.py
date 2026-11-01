"""Score model severity against the human ratings of the 40 reviewed aspects.

Usage: python3 -I scripts/score_model_vs_human.py <model_labels.jsonl> <human_sheet.csv> <key.csv> [<baseline_model_labels.jsonl>]
For each rated aspect we find the model's aspect with the same category in the same review
(ties broken by word overlap of the aspect names). No such aspect counts as 'not_found'.
"""
import csv
import json
import re
import sys

LEVELS = ["none", "low", "medium", "high", "critical"]


def toks(s):
    return set(re.findall(r"\w+", s.lower()))


def model_severity(labels, rid, category, name):
    cands = [a for a in labels.get(rid, {}).get("aspects", []) if a["category"] == category]
    if not cands:
        return "not_found"
    best = max(cands, key=lambda a: len(toks(a["aspect"]) & toks(name)))
    return best["severity"]


def run(label_path, sheet, key):
    labels = {json.loads(l)["reviewId"]: json.loads(l) for l in open(label_path) if l.strip()}
    out = []
    for row, k in key.items():
        human = sheet[row]["your_severity"].strip().lower()
        asp = labels.get(k["review_id"], {}).get("aspects", [])
        top = max((a["severity"] for a in asp), key=LEVELS.index) if asp else "none"
        out.append((row, human, model_severity(labels, k["review_id"], sheet[row]["category"],
                                               sheet[row]["aspect_to_rate"]), top))
    return out


def report(name, rows):
    crit = [r for r in rows if r[1] == "critical"]
    hit = sum(1 for r in crit if r[2] == "critical")
    found = [r for r in rows if r[2] != "not_found"]
    exact = sum(1 for r in found if r[1] == r[2])
    near = sum(1 for r in found if abs(LEVELS.index(r[1]) - LEVELS.index(r[2])) <= 1)
    low_critical = [r for r in rows if r[2] == "critical" and r[1] in ("none", "low", "medium")]
    top_hit = sum(1 for r in crit if r[3] == "critical")
    print("%s\n  critical recall vs human, strict (same category): %d of %d (%.0f%%) | not found: %d" %
          (name, hit, len(crit), 100 * hit / len(crit), sum(1 for r in rows if r[2] == "not_found")))
    print("  critical recall, review level (any aspect critical): %d of %d (%.0f%%)" %
          (top_hit, len(crit), 100 * top_hit / len(crit)))
    print("  severity agreement with human: exact %.0f%%, within one level %.0f%% (n=%d)" %
          (100 * exact / len(found), 100 * near / len(found), len(found)))
    print("  model said critical but human rated low or medium: %d" % len(low_critical))


sheet = {r["row"]: r for r in csv.DictReader(open(sys.argv[2], encoding="utf-8-sig"))}
key = {r["row"]: r for r in csv.DictReader(open(sys.argv[3], encoding="utf-8-sig"))}
if len(sys.argv) > 4:
    report("BEFORE (%s)" % sys.argv[4], run(sys.argv[4], sheet, key))
report("MODEL (%s)" % sys.argv[1], run(sys.argv[1], sheet, key))
