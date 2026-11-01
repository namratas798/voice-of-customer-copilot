"""Agreement between two independent labelers on the same reviews (neither is treated as truth).

Usage: python3 -I scripts/compare_labelers.py <inputs.jsonl> <labels_A.jsonl> <labels_B.jsonl> [nameA] [nameB]
Only reviews labeled by both are compared. Severity in both files was derived by the same code rules.
"""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc import metrics  # noqa: E402
from voc.schema import IMPACT_FLAGS, SEVERITIES  # noqa: E402

inputs_p, a_p, b_p = sys.argv[1:4]
na = sys.argv[4] if len(sys.argv) > 4 else "A"
nb = sys.argv[5] if len(sys.argv) > 5 else "B"
read = lambda p: {json.loads(l)["reviewId"]: json.loads(l) for l in open(p) if l.strip()}  # noqa: E731
A, B = read(a_p), read(b_p)
ids = [json.loads(l)["reviewId"] for l in open(inputs_p) if json.loads(l)["reviewId"] in A and json.loads(l)["reviewId"] in B]
print("reviews labeled by both %s and %s: %d (%s has %d labels, %s has %d)" % (na, nb, len(ids), na, len(A), nb, len(B)))

m = metrics.evaluate(A, B, ids)
f = lambda x: "n/a" if x is None else "%.2f" % x  # noqa: E731
print("\nusable: precision %s recall %s (%s taken as reference)" % (f(m["usable"]["precision"]), f(m["usable"]["recall"]), na))
print("aspect agreement F1 %s | review-level category F1 %s | category macro-F1 %s" %
      (f(m["aspect"]["f1"]), f(m["review_level_category"]["f1"]), f(m["category_macro_f1"])))
print("sentiment kappa %s | severity weighted kappa %s (on matched aspects)" %
      (f(m["sentiment_kappa"]), f(m["severity_weighted_kappa"])))


ua = sum(1 for i in ids if A[i]["usable"] == B[i]["usable"])
print("usable agreement: %.0f%% (%d of %d reviews)" % (100 * ua / len(ids), ua, len(ids)))


def problems_only(label):
    x = copy.deepcopy(label)
    x["aspects"] = [a for a in x["aspects"] if a["category"] not in ("praise", "other")]
    return x


mp = metrics.evaluate({i: problems_only(A[i]) for i in ids}, {i: problems_only(B[i]) for i in ids}, ids)
print("PROBLEMS ONLY (praise and other removed): aspect precision %s | recall %s | F1 %s | sentiment kappa %s | severity weighted kappa %s" %
      (f(mp["aspect"]["precision"]), f(mp["aspect"]["recall"]), f(mp["aspect"]["f1"]), f(mp["sentiment_kappa"]), f(mp["severity_weighted_kappa"])))
print("   (%s is the reference: precision = matched / %s problems = %d / %d, recall = matched / %s problems = %d / %d)" %
      (na, nb, mp["aspect"]["tp"], mp["aspect"]["tp"] + mp["aspect"]["fp"], na, mp["aspect"]["tp"], mp["aspect"]["tp"] + mp["aspect"]["fn"]))


def top(label):
    asp = label["aspects"]
    return max((x["severity"] for x in asp), key=SEVERITIES.index) if asp else "none"


ra, rb = [top(A[i]) for i in ids], [top(B[i]) for i in ids]
both = sum(1 for x, y in zip(ra, rb) if x == y == "critical")
only_a = sum(1 for x, y in zip(ra, rb) if x == "critical" and y != "critical")
only_b = sum(1 for x, y in zip(ra, rb) if y == "critical" and x != "critical")
neither = len(ids) - both - only_a - only_b
ka = metrics.cohen_kappa(["c" if x == "critical" else "n" for x in ra], ["c" if y == "critical" else "n" for y in rb], ["n", "c"])
print("\nREVIEW-LEVEL CRITICAL: both %d | only %s %d | only %s %d | neither %d | kappa %s" %
      (both, na, only_a, nb, only_b, neither, f(ka)))
ex = sum(1 for x, y in zip(ra, rb) if x == y)
nr = sum(1 for x, y in zip(ra, rb) if abs(SEVERITIES.index(x) - SEVERITIES.index(y)) <= 1)
print("review-level severity: exact %.0f%%, within one level %.0f%% (n=%d)" % (100 * ex / len(ids), 100 * nr / len(ids), len(ids)))

print("\nIMPACT FLAG AGREEMENT on matched aspects (agree %% | both true | only %s | only %s):" % (na, nb))
pairs = []
for i in ids:
    for gi, pi in metrics.match_aspects(A[i]["aspects"], B[i]["aspects"]):
        pairs.append((A[i]["aspects"][gi]["impact"], B[i]["aspects"][pi]["impact"]))
for flag in IMPACT_FLAGS:
    bt = sum(1 for x, y in pairs if x[flag] and y[flag])
    oa = sum(1 for x, y in pairs if x[flag] and not y[flag])
    ob = sum(1 for x, y in pairs if y[flag] and not x[flag])
    print("  %-24s %3.0f%% | %3d | %3d | %3d" % (flag, 100 * (len(pairs) - oa - ob) / max(1, len(pairs)), bt, oa, ob))
print("  (matched aspect pairs: %d)" % len(pairs))
