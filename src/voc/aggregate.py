"""Deterministic ranking: severity score, trend, priority and rating drag per theme.

Formulas follow docs/system_spec.md 4.6. No model is involved. Reviews outside the labeled sample
are not counted, so shares are only meaningful if the input reviews are representative.
"""
from __future__ import annotations

from .schema import SEV_WEIGHT

TREND_MIN, TREND_MAX = 0.5, 2.0


def review_severity(aspects: list, weights: dict = None) -> str:
    """Highest severity among a review's aspects in one theme."""
    w = weights or SEV_WEIGHT
    return max((a["severity"] for a in aspects), key=lambda s: w[s])


def _in_window(r: dict, start: str, end: str) -> bool:
    return start <= r["date"] <= end


def rank_themes(reviews: list, aspects: list, themes: list, start: str, end: str,
                prev_start: str = "", prev_end: str = "", weights: dict = None, min_size: int = 5) -> list:
    """reviews: dicts with review_id, date, score. aspects: dicts with review_id, severity, theme_id.

    Returns one dict per theme, sorted by priority (highest first).
    """
    win = {r["review_id"]: r for r in reviews if _in_window(r, start, end)}
    prev = {r["review_id"]: r for r in reviews if prev_start and _in_window(r, prev_start, prev_end)}
    n_total = len(win)
    by_theme = {}
    for a in aspects:
        if a.get("theme_id"):
            by_theme.setdefault(a["theme_id"], []).append(a)
    info = {t["theme_id"]: t for t in themes}
    out = []
    for tid, asp in by_theme.items():
        per_review = {}
        for a in asp:
            if a["review_id"] in win:
                per_review.setdefault(a["review_id"], []).append(a)
        if not per_review:
            continue
        count = len(per_review)
        prev_count = len({a["review_id"] for a in asp if a["review_id"] in prev})
        w = weights or SEV_WEIGHT
        score = sum(w[review_severity(v, w)] for v in per_review.values())
        trend = (count + 1) / (prev_count + 1) if prev_start else 1.0  # no previous window: neutral
        mult = max(TREND_MIN, min(TREND_MAX, trend))
        others = [r["score"] for rid, r in win.items() if rid not in per_review]
        r_other = sum(others) / len(others) if others else 0.0
        drag = sum(max(0.0, r_other - win[rid]["score"]) for rid in per_review) / n_total if n_total else 0.0
        t = info.get(tid, {})
        out.append({"theme_id": tid, "name": t.get("name", tid), "category": t.get("category", ""),
                    "status": "ranked" if count >= min_size else "emerging", "reviews": count,
                    "share": count / n_total if n_total else 0.0, "severity_score": score,
                    "prev_reviews": prev_count, "trend": trend, "priority": score * mult,
                    "rating_drag": drag})
    return sorted(out, key=lambda x: (x["status"] != "ranked", -x["priority"]))
