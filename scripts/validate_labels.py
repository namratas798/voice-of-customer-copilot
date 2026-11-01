"""Validate a labels file against the labeling guide's rules.

Usage: python3 -I scripts/validate_labels.py <input_reviews.jsonl> <labels.jsonl>
Exits 1 if any error is found. The rules live in src/voc/validate.py.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc.validate import validate_files  # noqa: E402

n_in, n_lab, errors = validate_files(sys.argv[1], sys.argv[2])
print("input reviews: %d | labeled: %d | errors: %d" % (n_in, n_lab, len(errors)))
for e in errors[:50]:
    print(" -", e)
if len(errors) > 50:
    print(" ... and %d more" % (len(errors) - 50))
sys.exit(1 if errors else 0)
