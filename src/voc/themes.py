"""Group aspects into themes within each category. Pure Python, no model download.

The extractor already writes each problem as a short English phrase (even for Hinglish reviews),
so similarity on those phrases is enough for a first version. Method: TF-IDF vectors on the phrase
words, average-linkage agglomerative clustering, merge while similarity >= threshold.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = set("a an the of to in on for and or is are was were be been it its this that with my me i we you "
           "not no app groww very too so at as by from but can cant cannot do does did dont has have had "
           "when while after before will would should user users".split())


def stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
            return w[: -len(suf)]
    return w


def tokens(text: str) -> list:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


def tfidf(docs: list) -> list:
    """docs: list of token lists. Returns L2-normalised sparse vectors (dicts)."""
    n = len(docs)
    df = Counter(t for d in docs for t in set(d))
    vecs = []
    for d in docs:
        v = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in set(d)}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def cluster(vecs: list, threshold: float) -> list:
    """Average-linkage agglomerative clustering. Returns a list of index lists."""
    n = len(vecs)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            sim[i][j] = sim[j][i] = cosine(vecs[i], vecs[j])
    members = {i: [i] for i in range(n)}
    while len(members) > 1:
        best, bi, bj = -1.0, -1, -1
        ids = list(members)
        for x in range(len(ids)):
            row = sim[ids[x]]
            for y in range(x + 1, len(ids)):
                if row[ids[y]] > best:
                    best, bi, bj = row[ids[y]], ids[x], ids[y]
        if best < threshold:
            break
        si, sj = len(members[bi]), len(members[bj])
        for k in members:
            if k in (bi, bj):
                continue
            sim[bi][k] = sim[k][bi] = (si * sim[bi][k] + sj * sim[bj][k]) / (si + sj)
        members[bi] += members.pop(bj)
    return list(members.values())


def build_themes(aspects: list, threshold: float = 0.35, min_size: int = 5) -> list:
    """aspects: list of dicts with category, aspect, review_id. Adds theme_id to each aspect in place.

    Returns a list of theme dicts: theme_id, category, name, size, review_count, status, samples.
    status is 'ranked' when the theme has at least min_size distinct reviews, else 'emerging'.
    """
    themes, by_cat = [], {}
    for idx, a in enumerate(aspects):
        a["theme_id"] = None
        by_cat.setdefault(a["category"], []).append(idx)
    for cat, idxs in sorted(by_cat.items()):
        vecs = tfidf([tokens(aspects[i]["aspect"]) for i in idxs])
        groups = sorted(cluster(vecs, threshold), key=len, reverse=True)
        for g_no, group in enumerate(groups, 1):
            tid = "%s:%d" % (cat, g_no)
            member_idx = [idxs[i] for i in group]
            # representative = the phrase most similar to the rest of the group
            rep = max(group, key=lambda i: sum(cosine(vecs[i], vecs[j]) for j in group))
            for m in member_idx:
                aspects[m]["theme_id"] = tid
            reviews = {aspects[m]["review_id"] for m in member_idx}
            themes.append({"theme_id": tid, "category": cat, "name": aspects[idxs[rep]]["aspect"],
                           "size": len(member_idx), "review_count": len(reviews),
                           "status": "ranked" if len(reviews) >= min_size else "emerging",
                           "samples": [aspects[m]["aspect"] for m in member_idx[:4]]})
    return themes
