"""Evaluation metrics. Aspect matching rule: same category and quote token Jaccard >= 0.5."""
from __future__ import annotations

import re
from collections import defaultdict

from .schema import CATEGORIES, NON_PRODUCT, SENTIMENTS, SEVERITIES

EMPTY = {"usable": False, "overall_sentiment": "neutral", "aspects": []}


def _tokens(s: str) -> set:
    return set(re.findall(r"\w+", s.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0


def overlap(a: str, b: str) -> float:
    """|A and B| / min(|A|, |B|) on word sets. A short quote inside a long one scores 1.0."""
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0


def match_aspects(gold: list, pred: list, thr: float = 0.5, mode: str = "overlap") -> list:
    """Greedy one-to-one matching on same category plus quote overlap (rule v2, see
    docs/eval_changelog.md). mode='jaccard' reproduces the stricter v1 rule.
    Returns list of (gold_index, pred_index)."""
    score = overlap if mode == "overlap" else jaccard
    pairs, used = [], set()
    for gi, g in enumerate(gold):
        best, best_s = None, 0.0
        for pi, p in enumerate(pred):
            if pi in used or p["category"] != g["category"]:
                continue
            s = score(g["quote"], p["quote"])
            if s >= thr and s > best_s:
                best, best_s = pi, s
        if best is not None:
            used.add(best)
            pairs.append((gi, best))
    return pairs


def cohen_kappa(a: list, b: list, labels: list, weights: str = ""):
    n, k = len(a), len(labels)
    if n == 0:
        return None
    idx = {l: i for i, l in enumerate(labels)}
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i, j):
        if i == j:
            return 0.0
        return abs(i - j) / (k - 1) if weights == "linear" else 1.0

    num = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    den = sum(w(i, j) * row[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    return None if den == 0 else 1 - num / den


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn}


def evaluate(gold: dict, pred: dict, ids: list) -> dict:
    """gold, pred: reviewId -> label. A missing prediction counts as an empty label."""
    u = [0, 0, 0]  # tp fp fn for usable=True
    a_tp = a_fp = a_fn = 0
    per_cat = defaultdict(lambda: [0, 0, 0])
    sent_g, sent_p, sev_g, sev_p = [], [], [], []
    crit_total = crit_hit = 0
    rc = [0, 0, 0]  # review-level category set micro tp fp fn
    missing = 0
    for rid in ids:
        g = gold[rid]
        p = pred.get(rid)
        if p is None:
            missing += 1
            p = EMPTY
        gu, pu = g["usable"], p["usable"]
        u[0] += gu and pu
        u[1] += (not gu) and pu
        u[2] += gu and (not pu)
        pairs = match_aspects(g["aspects"], p["aspects"])
        a_tp += len(pairs)
        a_fp += len(p["aspects"]) - len(pairs)
        a_fn += len(g["aspects"]) - len(pairs)
        matched_g = {gi for gi, _ in pairs}
        matched_p = {pi for _, pi in pairs}
        for gi, ga in enumerate(g["aspects"]):
            per_cat[ga["category"]][0 if gi in matched_g else 2] += 1
            if ga["severity"] == "critical":
                crit_total += 1
        for pi, pa in enumerate(p["aspects"]):
            if pi not in matched_p:
                per_cat[pa["category"]][1] += 1
        for gi, pi in pairs:
            ga, pa = g["aspects"][gi], p["aspects"][pi]
            sent_g.append(ga["sentiment"]); sent_p.append(pa["sentiment"])
            sev_g.append(ga["severity"]); sev_p.append(pa["severity"])
            if ga["severity"] == "critical" and pa["severity"] == "critical":
                crit_hit += 1
        gs = {a["category"] for a in g["aspects"]}
        ps = {a["category"] for a in p["aspects"]}
        rc[0] += len(gs & ps); rc[1] += len(ps - gs); rc[2] += len(gs - ps)
    cats = {c: _prf(*per_cat[c]) for c in CATEGORIES if per_cat[c] != [0, 0, 0]}
    f1s = [v["f1"] for v in cats.values() if v["f1"] is not None]
    return {
        "n": len(ids), "missing_predictions": missing,
        "usable": _prf(*u),
        "aspect": _prf(a_tp, a_fp, a_fn),
        "category_macro_f1": sum(f1s) / len(f1s) if f1s else None,
        "per_category": cats,
        "review_level_category": _prf(*rc),
        "sentiment_kappa": cohen_kappa(sent_g, sent_p, SENTIMENTS),
        "severity_weighted_kappa": cohen_kappa(sev_g, sev_p, SEVERITIES, "linear"),
        "critical_recall": (crit_hit / crit_total) if crit_total else None,
        "critical_gold_n": crit_total,
    }


def length_bucket(text: str) -> str:
    n = len(text.split())
    return "<8w" if n < 8 else ("8-19w" if n < 20 else "20w+")


def actionable(label: dict) -> bool:
    """Gold review that a PM could act on: usable with any aspect beyond praise/other."""
    return bool(label["usable"]) and any(a["category"] not in ("praise", "other") for a in label["aspects"])
