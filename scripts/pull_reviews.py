"""Pull Play Store reviews newest-first until a cutoff date.

usage: python pull_reviews.py <out.json> [package] [since YYYY-MM-DD]
"""
import json, sys, time
from datetime import datetime
from google_play_scraper import reviews, Sort, app

out_path = sys.argv[1]
pkg = sys.argv[2] if len(sys.argv) > 2 else "com.nextbillion.groww"
since = datetime.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else None

info = app(pkg, lang="en", country="in")
print("app:", info["title"], "| ratings:", info["ratings"], "| reviews:", info["reviews"])

out, tok = [], None
while True:
    batch, tok = reviews(pkg, lang="en", country="in", sort=Sort.NEWEST, count=200, continuation_token=tok)
    if not batch:
        break
    out += batch
    if since and batch[-1]["at"] < since:
        break
    if not tok:
        break
    if len(out) % 2000 == 0:
        print("pulled", len(out), "back to", batch[-1]["at"].date(), flush=True)
    time.sleep(0.5)

if since:
    out = [r for r in out if r["at"] >= since]
for r in out:
    r["at"] = r["at"].isoformat()
    r["repliedAt"] = r["repliedAt"].isoformat() if r.get("repliedAt") else None
json.dump(out, open(out_path, "w"), ensure_ascii=False)
print("saved", len(out), "reviews to", out_path)
