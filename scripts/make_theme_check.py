"""Build the theme coherence sheet for the product owner (about 2 minutes).

Usage: python3 -I scripts/make_theme_check.py <snapshot.json> <out.csv>
One row per ranked theme with its real problem phrases. The owner marks each yes or no.
"""
import csv
import json
import sys

snap = json.load(open(sys.argv[1]))
phrases = {}
for a in snap["aspects"]:
    if a.get("theme_id"):
        phrases.setdefault(a["theme_id"], []).append(a["aspect"])
rows = sorted([t for t in snap["themes"] if t["status"] == "ranked"], key=lambda t: -t["review_count"])
with open(sys.argv[2], "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["row", "theme_name", "category", "reviews", "problem_phrases_inside_it", "one_problem_yes_or_no", "your_note"])
    for i, t in enumerate(rows, 1):
        ph = phrases.get(t["theme_id"], [])
        w.writerow([i, t["name"], t["category"], t["review_count"], " | ".join(ph[:14]) + (" | ..." if len(ph) > 14 else ""), "", ""])
print("wrote %d themes to %s" % (len(rows), sys.argv[2]))
