"""Privacy and secrets scan. No model calls. Prints counts and masked context, never full personal data.

Usage: python3 -I scripts/privacy_scan.py
Checks: (1) personal data patterns inside review text that would be shown or published,
        (2) secret-looking strings in project files, (3) .env permissions and .gitignore coverage.
"""
import glob
import json
import os
import re
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

PII = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "upi id": re.compile(r"\b[\w.\-]{2,}@(?:ok\w+|ybl|paytm|upi|axl|ibl|sbi|apl|hdfcbank|icici)\b", re.I),
    "phone (10 digits)": re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"),
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "Aadhaar-like (12 digits)": re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"),
    "account-like number (9-18 digits)": re.compile(r"(?<!\d)\d{9,18}(?!\d)"),
    "link": re.compile(r"https?://\S+|www\.\S+"),
}
SECRET = [("Groq key", re.compile(r"gsk_[A-Za-z0-9]{20,}")), ("OpenAI-style key", re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
          ("Anthropic key", re.compile(r"(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_-]{20,}")), ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
          ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"))]


def mask(s):
    return re.sub(r"\d", "#", s)[:60]


def review_texts():
    """(source, id, text) for every review text that could be displayed or published."""
    for f in glob.glob("data/raw/*.json"):
        for r in json.load(open(f)):
            yield f, r["reviewId"], r["content"]
    snap = "app/snapshot.json"
    if os.path.exists(snap):
        for r in json.load(open(snap))["reviews"]:
            yield snap, r["review_id"], r["text"]


print("1. PERSONAL DATA INSIDE REVIEW TEXT")
seen, hits = set(), {}
for src, rid, text in review_texts():
    if (src.startswith("app/"), rid) in seen:
        continue
    for name, rx in PII.items():
        m = rx.search(text)
        if m:
            hits.setdefault((src, name), []).append((rid[:8], mask(m.group(0))))
    seen.add((src.startswith("app/"), rid))
if not hits:
    print("   none found")
for (src, name), items in sorted(hits.items()):
    print("   %-52s %-34s %3d review(s), e.g. %s" % (src, name, len(items), items[0]))

print("\n2. SECRET-LOOKING STRINGS IN PROJECT FILES (excluding .venv and .env)")
bad = 0
for dp, dn, fn in os.walk("."):
    dn[:] = [d for d in dn if d not in (".venv", "__pycache__", ".git", "node_modules")]
    for f in fn:
        path = os.path.join(dp, f)
        if f == ".env" or os.path.getsize(path) > 5_000_000 or f.endswith((".db", ".pyc", ".png", ".jpg")):
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for name, rx in SECRET:
            if rx.search(text):
                bad += 1
                print("   FOUND %s in %s" % (name, path))
print("   none found" if not bad else "   %d problem(s)" % bad)

print("\n3. KEY FILE AND GITIGNORE")
if os.path.exists(".env"):
    mode = stat.S_IMODE(os.stat(".env").st_mode)
    print("   .env exists, permissions %s (%s)" % (oct(mode), "owner only" if mode & 0o077 == 0 else "TOO OPEN"))
else:
    print("   no .env file")
need = [".env", ".venv/", "data/raw/", "data/llm_cache.db", "runs/", "app/snapshot.json", "data/golden/", "data/external_labeling/"]
gi = open(".gitignore").read().splitlines() if os.path.exists(".gitignore") else []
missing = [n for n in need if not any(n.rstrip("/") in g for g in gi)]
print("   .gitignore %s" % ("covers everything that should stay private" if not missing else "is missing: " + ", ".join(missing)))
sys.exit(1 if bad or missing else 0)
