"""Compare the human's severity ratings with Cursor's and the model's.

Usage: python3 -I scripts/score_adjudication.py <critical_review_sheet.csv> <adjudication_key.csv>
"""
import csv
import sys

LEVELS = ["none", "low", "medium", "high", "critical"]
sheet = {r["row"]: r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8-sig"))}
key = {r["row"]: r for r in csv.DictReader(open(sys.argv[2], encoding="utf-8-sig"))}

rated, bad = [], []
for row, k in key.items():
    h = (sheet[row]["your_severity"] or "").strip().lower()
    if not h:
        continue
    if h not in LEVELS:
        bad.append((row, h))
        continue
    rated.append((row, h, k["cursor_severity"], k["model_severity"]))
if bad:
    sys.exit("Unrecognised severity in rows %s. Use one of: %s" % (bad[:5], ", ".join(LEVELS)))
print("rated %d of %d rows" % (len(rated), len(key)))


def rate(pairs, label):
    if not pairs:
        return "%s: n/a" % label
    exact = sum(a == b for a, b in pairs) / len(pairs)
    near = sum(abs(LEVELS.index(a) - LEVELS.index(b)) <= 1 for a, b in pairs) / len(pairs)
    return "%s: exact %.0f%%, within one level %.0f%% (n=%d)" % (label, 100 * exact, 100 * near, len(pairs))


print(rate([(h, c) for _, h, c, _ in rated], "you vs Cursor"))
print(rate([(h, m) for _, h, _, m in rated if m != "not_found"], "you vs model "))

crit_rows = [r for r in rated if r[2] == "critical"]
print("\nOf the %d cases Cursor called critical, you rated:" % len(crit_rows))
for lvl in reversed(LEVELS):
    n = sum(1 for r in crit_rows if r[1] == lvl)
    if n:
        print("  %-8s %d" % (lvl, n))
yours = [r for r in rated if r[1] == "critical"]
print("\nYou rated %d cases critical in total. Cursor also said critical on %d, the model on %d." %
      (len(yours), sum(1 for r in yours if r[2] == "critical"), sum(1 for r in yours if r[3] == "critical")))
print("Cases where you went lower than Cursor: %d | higher: %d" %
      (sum(1 for r in rated if LEVELS.index(r[1]) < LEVELS.index(r[2])),
       sum(1 for r in rated if LEVELS.index(r[1]) > LEVELS.index(r[2]))))
