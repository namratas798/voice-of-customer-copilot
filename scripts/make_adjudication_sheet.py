"""Build the human severity review sheet for the dev-set gold-critical aspects.

Usage: python3 -I scripts/make_adjudication_sheet.py <gold.jsonl> <model_labels.jsonl> <inputs.jsonl> <out_dir>

Writes two files:
  critical_review_sheet.csv  what the human sees: review text, stars, aspect to rate, empty severity column.
                             Neither labeler's severity is shown, and critical cases are mixed with
                             non-critical controls so the sheet does not reveal which ones were critical.
  adjudication_key.csv       hidden key (do not open before rating): both labelers' severities.
"""
import csv
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc import metrics  # noqa: E402

gold_p, model_p, inputs_p, out_dir = sys.argv[1:5]
read = lambda p: {json.loads(l)["reviewId"]: json.loads(l) for l in open(p) if l.strip()}  # noqa: E731
gold, model, inputs = read(gold_p), read(model_p), read(inputs_p)

crit, ctrl = [], []
for rid, g in gold.items():
    pairs = dict(metrics.match_aspects(g["aspects"], model[rid]["aspects"]))
    for gi, a in enumerate(g["aspects"]):
        pi = pairs.get(gi)
        row = {"review_id": rid, "text": inputs[rid]["content"], "stars": inputs[rid]["score"],
               "category": a["category"], "aspect": a["aspect"], "cursor_severity": a["severity"],
               "model_severity": model[rid]["aspects"][pi]["severity"] if pi is not None else "not_found"}
        if a["severity"] == "critical":
            crit.append(row)
        elif a["severity"] in ("high", "medium") and a["sentiment"] == "negative":
            ctrl.append(row)

rng = random.Random(42)
rows = crit + rng.sample(ctrl, min(12, len(ctrl)))
rng.shuffle(rows)

pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
with open(out_dir + "/critical_review_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["row", "review_text", "stars", "category", "aspect_to_rate", "your_severity", "your_note"])
    for i, r in enumerate(rows, 1):
        w.writerow([i, r["text"], r["stars"], r["category"], r["aspect"], "", ""])
with open(out_dir + "/adjudication_key.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["row", "review_id", "cursor_severity", "model_severity", "is_cursor_critical"])
    for i, r in enumerate(rows, 1):
        w.writerow([i, r["review_id"], r["cursor_severity"], r["model_severity"], int(r["cursor_severity"] == "critical")])
print("rows: %d (critical %d + controls %d)" % (len(rows), len(crit), len(rows) - len(crit)))
