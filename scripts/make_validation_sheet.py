"""Draw a fresh validation sheet of reviews the product owner has not rated and the golden set does not contain.

Usage: python3 -I scripts/make_validation_sheet.py <raw_reviews.json> <out_dir>

The human rates ONE thing per review: how serious is the most serious problem it describes.
Writes validation_sheet.csv (what the human sees), validation_key.csv (hidden: review ids and how each
review was selected) and val30_inputs.jsonl (model input in the golden-set format).
"""
import csv
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc import gate, ingest  # noqa: E402

raw, out = sys.argv[1], sys.argv[2]
golden = set()
for f in ("data/golden/dev_for_ai.jsonl", "data/golden/test_for_ai.jsonl"):
    golden |= {json.loads(l)["reviewId"] for l in open(f)}

LIKELY = re.compile(r"money|paisa|paise|loss|lost|stuck|withdraw|refund|fraud|scam|stop.?loss|square|order|"
                    r"deduct|hack|kyc|aadhaar|pan |otp|blocked|debit|credit|charge", re.I)
pool_likely, pool_other = [], []
for r in ingest.load_reviews(raw):
    n = len(r["content"].split())
    if r["review_id"] in golden or not (8 <= n <= 120) or r["score"] > 3:
        continue
    if gate.gate(r["content"], r["score"])[0] != "pass":
        continue
    (pool_likely if LIKELY.search(r["content"]) else pool_other).append(r)

rng = random.Random(42)
picked = [(r, "likely_serious") for r in rng.sample(sorted(pool_likely, key=lambda r: r["review_id"]), 20)] + \
         [(r, "random_negative") for r in rng.sample(sorted(pool_other, key=lambda r: r["review_id"]), 10)]
rng.shuffle(picked)

pathlib.Path(out).mkdir(parents=True, exist_ok=True)
with open(out + "/validation_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["row", "review_text", "stars", "your_severity", "your_note"])
    for i, (r, _) in enumerate(picked, 1):
        w.writerow([i, r["content"], r["score"], "", ""])
with open(out + "/validation_key.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["row", "review_id", "selection"])
    for i, (r, how) in enumerate(picked, 1):
        w.writerow([i, r["review_id"], how])
with open(out + "/val30_inputs.jsonl", "w") as f:
    for r, _ in picked:
        f.write(json.dumps({"reviewId": r["review_id"], "content": r["content"], "score": r["score"],
                            "appVersion": r["app_version"], "date": r["date"]}, ensure_ascii=False) + "\n")
print("pools: likely_serious %d, random_negative %d | picked %d" % (len(pool_likely), len(pool_other), len(picked)))
