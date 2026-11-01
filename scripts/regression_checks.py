"""Does the release comparison cry wolf, and does it catch a real change? Simulations only, no model calls.

Usage: python3 -I scripts/regression_checks.py <sample_inputs.jsonl> <snapshot.json> [out.md]

1. No-change test: take real reviews from versions with 30+ reviews, shuffle which version each review belongs to
   (so any difference is pure chance), run the comparison, count how often it flags something.
2. Injected-spike test: make two versions with a known difference in the 1-2 star share, run the comparison
   many times, count how often the spike is flagged (power).
3. Same for one theme hiding among ~95 others (the multiple-tests case).
"""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc import regress  # noqa: E402

rows = [json.loads(l) for l in open(sys.argv[1])]
snap = json.load(open(sys.argv[2]))
out_path = sys.argv[3] if len(sys.argv) > 3 else None
lines = []


def say(s=""):
    print(s)
    lines.append(s)


reviews = [{"review_id": r["reviewId"], "version": r.get("appVersion") or "unknown", "score": r["score"]} for r in rows]
counts = {}
for r in reviews:
    counts[r["version"]] = counts.get(r["version"], 0) + 1
big = sorted([v for v, n in counts.items() if n >= regress.MIN_N and regress.version_key(v)], key=regress.version_key)
pool = [r for r in reviews if r["version"] in big]
sizes = [counts[v] for v in big]
themes_of = {}
for a in snap["aspects"]:
    if a.get("theme_id"):
        themes_of.setdefault(a["review_id"], []).append(a)
say("# Release comparison checks\n")
say("Versions used (30+ reviews each): " + ", ".join("%s (%d)" % (v, counts[v]) for v in big))
say("Rules under test: both versions need %d+ reviews, adjusted p < %.2f, and a rise of at least %.1fx.\n" %
    (regress.MIN_N, regress.ALPHA, regress.MIN_RATIO))

rng = random.Random(7)


def shuffled_versions():
    labels = [v for v, n in zip(big, sizes) for _ in range(n)]
    rng.shuffle(labels)
    return labels


# 1. no-change test, 1 to 2 star share only
N1 = 2000
false_alarms = 0
for _ in range(N1):
    labels = shuffled_versions()
    rv = [{"review_id": r["review_id"], "version": v, "score": r["score"]} for r, v in zip(pool, labels)]
    if any(c["flag"] for c in regress.compare(rv, []) if c["subject"] == "negative_share"):
        false_alarms += 1
say("## 1. No-change test (1 to 2 star share)")
say("%d shuffles of real reviews across %d versions, flags raised: **%d (%.1f%%)**. Any flag here is a false alarm.\n" %
    (N1, len(big), false_alarms, 100 * false_alarms / N1))

# 1b. no-change test including every theme (many comparisons at once)
N2 = 150
fa_theme = 0
for _ in range(N2):
    labels = shuffled_versions()
    rv = [{"review_id": r["review_id"], "version": v, "score": r["score"]} for r, v in zip(pool, labels)]
    asp = [a for r in pool for a in themes_of.get(r["review_id"], [])]
    if any(c["flag"] for c in regress.compare(rv, asp)):
        fa_theme += 1
say("## 1b. No-change test including all %d themes" % len({a["theme_id"] for v in themes_of.values() for a in v}))
say("%d shuffles, any flag (score or any theme): **%d (%.1f%%)**.\n" % (N2, fa_theme, 100 * fa_theme / N2))

# 2. injected spike on the 1 to 2 star share
say("## 2. Injected spike (1 to 2 star share)")
say("Previous version has 25%% of reviews at 1 to 2 stars. The new version has the share below. %d simulations each.\n" % 1000)
say("| New share | Rise | Reviews per version | Flagged |")
say("|---|---|---|---|")
for n in (80, 150):
    for p1 in (0.25, 0.30, 0.35, 0.40, 0.50, 0.60):
        hit = 0
        for _ in range(1000):
            a_bad = sum(rng.random() < 0.25 for _ in range(n))
            b_bad = sum(rng.random() < p1 for _ in range(n))
            rv = [{"review_id": "a%d" % i, "version": "18.1.0", "score": 1 if i < a_bad else 5} for i in range(n)] + \
                 [{"review_id": "b%d" % i, "version": "18.2.0", "score": 1 if i < b_bad else 5} for i in range(n)]
            hit += any(c["flag"] for c in regress.compare(rv, []))
        say("| %.0f%% | %s | %d | %.0f%% |" % (100 * p1, "none" if p1 == 0.25 else "%.1fx" % (p1 / 0.25), n, hit / 10))
say("\nThe 1.5x rule applies to the shares actually observed in each sample, so a small real rise is flagged only when chance also pushes the observed difference up. That is why 1.2x to 1.4x rows flag rarely, not never.\n")

# 3. one theme among many
say("## 3. One theme spikes among 95 others")
say("95 themes stay at 5% of reviews in both versions. One theme goes from 5% to the share below. 80 reviews per version, 500 simulations each.\n")
say("| Theme share in new version | Flagged |")
say("|---|---|")
n, m = 80, 96
for p1 in (0.05, 0.15, 0.20, 0.30, 0.40):
    hit = 0
    for _ in range(500):
        ps, ks = [], []
        for t in range(m):
            q = p1 if t == 0 else 0.05
            ka, kb = sum(rng.random() < 0.05 for _ in range(n)), sum(rng.random() < q for _ in range(n))
            ps.append(regress.fisher_exact(kb, n - kb, ka, n - ka))
            ks.append((ka, kb))
        adj = regress.bh_adjust(ps)
        ka, kb = ks[0]
        ratio = (kb / ka) if ka else float("inf")
        hit += adj[0] < regress.ALPHA and ratio >= regress.MIN_RATIO and kb > ka
    say("| %.0f%% | %.0f%% |" % (100 * p1, hit / 5))
say("\nNote: the 5% row is the no-change case for this theme.")
if out_path:
    open(out_path, "w").write("\n".join(lines) + "\n")
    print("\nsaved", out_path)
