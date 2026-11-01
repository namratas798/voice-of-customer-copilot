"""Release regression detection: is something worse in version V than in the previous version?

Rules (docs/system_spec.md 4.7, decided thresholds): both groups need at least MIN_N reviews, the
adjusted p-value must be below ALPHA, and the share must rise by at least MIN_RATIO. Otherwise the
result says why nothing is flagged. The 'unknown' version bucket is always reported separately.
"""
from __future__ import annotations

from math import comb

MIN_N, ALPHA, MIN_RATIO = 30, 0.01, 1.5


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p-value for the 2x2 table [[a, b], [c, d]]."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    if n == 0:
        return 1.0

    def p(x):
        return comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)

    lo, hi = max(0, r1 - (n - c1)), min(r1, c1)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs + 1e-12))


def bh_adjust(pvals: list) -> list:
    """Benjamini-Hochberg adjusted p-values, same order as the input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, prev = [0.0] * m, 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, pvals[i] * m / rank)
        adj[i] = prev
    return adj


def version_key(v: str):
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return None


def compare(reviews: list, aspects: list) -> list:
    """reviews: review_id, version, score. aspects: review_id, theme_id.

    Compares each version with the previous version that has at least MIN_N reviews (tiny hotfix versions
    in between are skipped as baselines) on (a) the share of 1-2 star reviews and (b) each theme's share.
    A version with fewer than MIN_N reviews gets one 'insufficient evidence' row against the version before it.
    """
    versions = sorted({r["version"] for r in reviews if version_key(r["version"])}, key=version_key)
    by_v = {v: [r for r in reviews if r["version"] == v] for v in versions}
    themes_of = {}
    for a in aspects:
        if a.get("theme_id"):
            themes_of.setdefault(a["review_id"], set()).add(a["theme_id"])

    def table(prev_v, v, subjects):
        A, B = by_v[prev_v], by_v[v]
        rows = []
        for name, f in subjects(A, B).items():
            ka, kb = sum(map(f, A)), sum(map(f, B))
            sa, sb = ka / len(A), kb / len(B)
            rows.append({"version": v, "baseline": prev_v, "subject": name, "n_base": len(A), "n_new": len(B),
                         "share_base": sa, "share_new": sb, "p": fisher_exact(kb, len(B) - kb, ka, len(A) - ka)})
        return rows

    def negatives(A, B):
        return {"negative_share": lambda r: r["score"] <= 2}

    def with_themes(A, B):
        subjects = negatives(A, B)
        for t in sorted({t for r in A + B for t in themes_of.get(r["review_id"], ())}):
            subjects["theme:" + t] = (lambda t: lambda r: t in themes_of.get(r["review_id"], ()))(t)
        return subjects

    results = []
    for i, v in enumerate(versions):
        base = next((b for b in reversed(versions[:i]) if len(by_v[b]) >= MIN_N), None)
        if len(by_v[v]) < MIN_N or base is None:
            if i == 0:
                continue
            for r in table(versions[i - 1], v, negatives):
                r.update(p_adj=r["p"], flag=False, why="insufficient evidence (n < %d)" % MIN_N)
                results.append(r)
            continue
        rows = table(base, v, with_themes)
        for r, q in zip(rows, bh_adjust([r["p"] for r in rows])):
            r["p_adj"] = q
            ratio = r["share_new"] / r["share_base"] if r["share_base"] else float("inf")
            r["flag"] = bool(q < ALPHA and ratio >= MIN_RATIO and r["share_new"] > r["share_base"])
            r["why"] = "flagged" if r["flag"] else "no significant rise"
            results.append(r)
    return results


def unknown_bucket(reviews: list) -> dict:
    u = [r for r in reviews if not version_key(r["version"])]
    return {"n": len(u), "negative_share": (sum(1 for r in u if r["score"] <= 2) / len(u)) if u else None}
