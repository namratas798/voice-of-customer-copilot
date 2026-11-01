"""Is anything real in what would be public? Run before publishing. Needs the real raw reviews on this machine.

Usage: python3 -I scripts/public_check.py
Checks every file that is not git-ignored, plus the demo snapshot, for runs of 6 consecutive words that also
occur in the real reviews. Prints the file and a masked-by-length excerpt of each hit, never the whole review.
"""
import fnmatch
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))
from voc import publiccheck  # noqa: E402

real = publiccheck.real_shingles()
if not real:
    sys.exit("No raw review files found in data/raw, so nothing to compare against. Run this on the machine that has them.")
print("compared against %d distinct six-word runs from the real reviews\n" % len(real))

ignore = [l.strip() for l in open(".gitignore") if l.strip() and not l.startswith("#")]


def ignored(path):
    p = path.replace(os.sep, "/")
    for pat in ignore:
        pat = pat.rstrip("/")
        if fnmatch.fnmatch(p, pat) or p.startswith(pat + "/") or ("/" + pat + "/") in ("/" + p) or fnmatch.fnmatch(os.path.basename(p), pat):
            return True
    return False


bad = 0
checked = 0
for dp, dn, fn in os.walk("."):
    dn[:] = [d for d in dn if d not in (".venv", ".git", "__pycache__", "node_modules")]
    for f in fn:
        path = os.path.relpath(os.path.join(dp, f), ".")
        if ignored(path) or f.endswith((".db", ".pyc", ".png", ".jpg", ".csv")) or os.path.getsize(path) > 3_000_000:
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if path.endswith(".json"):  # the demo snapshot: check only the review text
            try:
                data = json.load(open(path))
                text = " \n ".join(r["text"] for r in data.get("reviews", [])) if isinstance(data, dict) else text
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        checked += 1
        hits = publiccheck.overlaps(text, real)
        if hits:
            bad += 1
            print("REAL TEXT in %s: %d shared six-word run(s), e.g. \"%s\"" % (path, len(hits), hits[0]))
print("\nchecked %d publishable files: %s" % (checked, "all clear" if not bad else "%d file(s) contain real review text" % bad))
sys.exit(1 if bad else 0)
