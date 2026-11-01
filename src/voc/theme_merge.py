"""AI merge step for themes: decide which word-matching groups mean the same underlying problem.

The model only sees short problem phrases (no reviewer data) and can only combine groups that already
exist. Safety rules, enforced in code: every group id used must be one we offered (invented ids are
dropped and counted), every offered group ends up in exactly one theme (anything the model forgets stays
as its own theme), and merging never crosses categories.
"""
from __future__ import annotations

import json

SYSTEM = """You group short problem phrases from app-store reviews into themes for a product manager.
Each line below is a cluster: id | number of reviews | example phrases.
Merge clusters only when they describe the same underlying problem or request, meaning the same thing a
product team would fix or build. Do not merge clusters about different problems, even if they share a word.
A cluster that matches no other stays alone as its own group. Every cluster id must appear in exactly one
group. Name each group in at most 8 words, plain and neutral: describe the problem, not blame, and for
fraud or money-loss statements say 'claims'. Return JSON only."""

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["groups"],
    "properties": {"groups": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["name", "cluster_ids"],
        "properties": {"name": {"type": "string"}, "cluster_ids": {"type": "array", "items": {"type": "string"}}}}}},
}


def _lines(clusters: list) -> str:
    out = []
    for i, c in enumerate(clusters, 1):
        out.append("c%d | %d reviews | %s" % (i, c["review_count"], "; ".join(c["samples"][:3])))
    return "\n".join(out)


def validate_groups(groups: list, n_clusters: int):
    """Return (groups as lists of 0-based cluster indexes with names, dropped_unknown, added_missing)."""
    valid = {"c%d" % i: i - 1 for i in range(1, n_clusters + 1)}
    seen, out, dropped = set(), [], 0
    for g in groups:
        idx = []
        for cid in g.get("cluster_ids", []):
            if cid in valid and cid not in seen:
                seen.add(cid)
                idx.append(valid[cid])
            else:
                dropped += 1
        if idx:
            out.append({"name": (g.get("name") or "").strip(), "members": idx})
    missing = [i for cid, i in valid.items() if cid not in seen]
    for i in missing:
        out.append({"name": "", "members": [i]})
    return out, dropped, len(missing)


def merge_category(llm, model: str, category: str, clusters: list):
    """Returns (groups, report). groups: list of {'name', 'members' (indexes into clusters)}."""
    if len(clusters) < 2:
        return [{"name": "", "members": [i]} for i in range(len(clusters))], {"skipped": True}
    user = "Category: %s\n%s" % (category, _lines(clusters))
    res = llm.call(model=model, system=SYSTEM, user=user, schema=SCHEMA, effort="low", max_tokens=3500)
    try:
        groups = json.loads(res.text).get("groups", [])
    except (json.JSONDecodeError, AttributeError):
        groups = []
    out, dropped, added = validate_groups(groups, len(clusters))
    return out, {"clusters_in": len(clusters), "groups_out": len(out), "dropped_unknown_ids": dropped,
                 "forgotten_kept_alone": added, "tokens": res.usage, "cached": res.cached}


def merge_all(llm, model: str, aspects: list, themes: list, min_size: int = 5):
    """Merge within each category. Returns (new_themes, per_category_report). Rewrites aspect theme_ids."""
    by_cat = {}
    for t in themes:
        by_cat.setdefault(t["category"], []).append(t)
    old_to_new, new_themes, reports = {}, [], {}
    for cat, clusters in sorted(by_cat.items()):
        groups, rep = merge_category(llm, model, cat, clusters)
        reports[cat] = rep
        built = []
        for g in groups:
            members = [clusters[i] for i in g["members"]]
            biggest = max(members, key=lambda c: c["review_count"])
            built.append({"name": g["name"] or biggest["name"], "members": members})
        # review counts after merging need the aspects; compute from them
        for b in built:
            ids = {m["theme_id"] for m in b["members"]}
            b["reviews"] = {a["review_id"] for a in aspects if a.get("theme_id") in ids}
        built.sort(key=lambda b: len(b["reviews"]), reverse=True)
        for k, b in enumerate(built, 1):
            tid = "%s:%d" % (cat, k)
            for m in b["members"]:
                old_to_new[m["theme_id"]] = tid
            samples = [s for m in b["members"] for s in m["samples"]][:5]
            new_themes.append({"theme_id": tid, "category": cat, "name": b["name"], "size": sum(m["size"] for m in b["members"]),
                               "review_count": len(b["reviews"]), "merged_from": len(b["members"]),
                               "status": "ranked" if len(b["reviews"]) >= min_size else "emerging", "samples": samples})
    for a in aspects:
        if a.get("theme_id") in old_to_new:
            a["theme_id"] = old_to_new[a["theme_id"]]
    return new_themes, reports


def coverage(aspects: list, themes: list) -> float:
    """Share of reviews with a problem aspect that sit in at least one ranked theme."""
    ranked = {t["theme_id"] for t in themes if t["status"] == "ranked"}
    all_r = {a["review_id"] for a in aspects}
    in_r = {a["review_id"] for a in aspects if a.get("theme_id") in ranked}
    return len(in_r) / len(all_r) if all_r else 0.0
