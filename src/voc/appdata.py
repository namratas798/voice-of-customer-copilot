"""Plain-code functions behind the Streamlit app. No UI and no model calls here (except label_one)."""
from __future__ import annotations

import datetime
import json
from collections import Counter

from . import aggregate, regress
from .schema import SEV_WEIGHT


def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def previous_window(start: str, end: str):
    """The window of the same length that ends the day before `start`."""
    s, e = _d(start), _d(end)
    n = (e - s).days + 1
    pe = s - datetime.timedelta(days=1)
    return (pe - datetime.timedelta(days=n - 1)).isoformat(), pe.isoformat()


def headline(snap: dict, start: str, end: str) -> dict:
    rv = [r for r in snap["reviews"] if start <= r["date"] <= end]
    n = len(rv)
    with_problem = {a["review_id"] for a in snap["aspects"] if a.get("theme_id")}
    return {"reviews": n,
            "avg_rating": sum(r["score"] for r in rv) / n if n else 0.0,
            "negative_share": sum(1 for r in rv if r["score"] <= 2) / n if n else 0.0,
            "problem_reviews": sum(1 for r in rv if r["review_id"] in with_problem)}


def ranking(snap: dict, start: str, end: str, weights: dict = None, min_size: int = 5, categories=None) -> tuple:
    """Returns (rows, trend_available). Trend is neutral when the previous window starts before the data does."""
    ps, pe = previous_window(start, end)
    trend_ok = ps >= snap["meta"]["date_from"]
    aspects = [a for a in snap["aspects"] if a.get("theme_id")]
    rows = aggregate.rank_themes(snap["reviews"], aspects, snap["themes"], start, end,
                                 ps if trend_ok else "", pe if trend_ok else "", weights, min_size)
    if categories:
        rows = [r for r in rows if r["category"] in categories]
    return rows, trend_ok


def theme_detail(snap: dict, theme_id: str, start: str, end: str) -> dict:
    by_review = {}
    for a in snap["aspects"]:
        if a.get("theme_id") == theme_id:
            by_review.setdefault(a["review_id"], []).append(a)
    rmap = {r["review_id"]: r for r in snap["reviews"]}
    items = []
    for rid, asp in by_review.items():
        r = rmap[rid]
        if not (start <= r["date"] <= end):
            continue
        sev = aggregate.review_severity(asp)
        items.append({"review_id": rid, "date": r["date"], "version": r["version"], "stars": r["score"], "text": r["text"],
                      "severity": sev, "aspects": [{"phrase": a["aspect"], "quote": a["quote"],
                                                    "flags": [k for k, v in (a.get("impact") or {}).items() if v]} for a in asp]})
    items.sort(key=lambda x: x["date"], reverse=True)               # newest first ...
    items.sort(key=lambda x: -SEV_WEIGHT[x["severity"]])            # ... then most severe first (stable)
    weeks = Counter()
    for it in items:
        d = _d(it["date"])
        weeks[(d - datetime.timedelta(days=d.weekday())).isoformat()] += 1
    return {"reviews": items, "severity_mix": dict(Counter(i["severity"] for i in items)),
            "by_week": dict(sorted(weeks.items())), "by_version": dict(Counter(i["version"] for i in items).most_common())}


def release_table(snap: dict) -> dict:
    rv = [{"review_id": r["review_id"], "version": r["version"], "score": r["score"]} for r in snap["reviews"]]
    aspects = [a for a in snap["aspects"] if a.get("theme_id")]
    by_v = {}
    for r in rv:
        by_v.setdefault(r["version"], []).append(r["score"])
    rows = [{"version": v, "reviews": len(s), "avg_rating": sum(s) / len(s), "negative_share": sum(1 for x in s if x <= 2) / len(s)}
            for v, s in by_v.items() if regress.version_key(v)]
    rows.sort(key=lambda r: regress.version_key(r["version"]))
    comps = [r for r in regress.compare(rv, aspects) if min(r["n_base"], r["n_new"]) >= regress.MIN_N]
    return {"versions": rows, "comparisons": comps, "unknown": regress.unknown_bucket(rv), "min_n": regress.MIN_N}


def live_cache_path() -> str:
    """Where the live feature keeps its small cache. A temporary folder, because a host's checkout has no data/ folder."""
    import os
    import tempfile
    return os.path.join(tempfile.gettempdir(), "voc_live_cache.db")


def label_one(text: str, stars: int, root: str = "."):
    """Live labeling of one pasted review with the pipeline's own extractor. Returns (label or None, errors)."""
    from . import extract
    from .llm import LLM
    llm = LLM(live_cache_path(), wait_on_daily=False)
    review = {"reviewId": "pasted", "content": text.strip(), "score": int(stars)}
    system = extract.build_system(root, mode="flags")
    res = extract.extract_review(llm, review, system, ["openai/gpt-oss-20b"], "low", mode="flags")
    return res["label"], res["errors"]


FACT_NAMES = {
    "money_lost": "money lost", "money_blocked": "money stuck or delayed", "loss_amount_stated": "an amount was stated",
    "order_wrong": "an order went wrong", "core_action_blocked": "couldn't complete a main action",
    "workaround_mentioned": "a workaround was mentioned", "security_or_data_issue": "security or data problem",
}


def plain_facts(impact: dict) -> list:
    """Facts worth showing a user, in plain words. 'event_described' is left out: it only says the review describes
    something that happened, so it is true for almost every complaint and tells the reader nothing."""
    return [FACT_NAMES[k] for k in FACT_NAMES if (impact or {}).get(k)]


# ------------------------------------------------------------------------------------------------
# Weekly brief: every number comes from code, every quote is word for word from a real review.

def excerpt(text: str, limit: int = 220) -> str:
    """A prefix of the review, cut at a word boundary. Still word for word, marked with an ellipsis when cut."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"


def _short_id(rid: str) -> str:
    """Short id for display: the first 8 characters of a long id, but never cut a short id (it would become ambiguous)."""
    return rid if len(rid) <= 10 else rid[:8]


def _ver(v: str) -> str:
    return "no app version" if v == "unknown" else "v" + v


def _pretty(date_s: str) -> str:
    return _d(date_s).strftime("%b %d").replace(" 0", " ")


def build_brief(snap: dict, start: str, end: str, weights: dict = None, min_size: int = 5) -> dict:
    """Structured brief for one period. Non-product categories (fraud claims, customer support) never enter the fix list."""
    ps, pe = previous_window(start, end)
    trend_ok = ps >= snap["meta"]["date_from"]
    head = headline(snap, start, end)
    prev = headline(snap, ps, pe) if trend_ok else None
    rows, _ = ranking(snap, start, end, weights, min_size)
    ranked = [r for r in rows if r["status"] == "ranked"]

    def item(r):
        det = theme_detail(snap, r["theme_id"], start, end)
        mix = det["severity_mix"]
        quotes = [{"review_id": it["review_id"], "date": it["date"], "stars": it["stars"], "version": it["version"],
                   "severity": it["severity"], "excerpt": excerpt(it["text"])} for it in det["reviews"][:2]]
        return {"theme_id": r["theme_id"], "name": r["name"], "category": r["category"], "reviews": r["reviews"],
                "share": r["share"], "serious": mix.get("critical", 0) + mix.get("high", 0),
                "prev_reviews": r["prev_reviews"] if trend_ok else None, "trend": r["trend"] if trend_ok else None,
                "rating_lift": r["rating_drag"], "quotes": quotes,
                "small_sample": r["reviews"] < 30}

    product = [item(r) for r in ranked if r["category"] not in ("fraud_money_loss_claim", "customer_support")]
    fixes = [t for t in product if t["category"] != "feature_request"]
    asks = [t for t in product if t["category"] == "feature_request"]
    risk = [item(r) for r in ranked if r["category"] == "fraud_money_loss_claim"]
    support = [item(r) for r in ranked if r["category"] == "customer_support"]
    rising = [t for t in product if trend_ok and t["trend"] is not None and t["trend"] >= 1.5]
    rt = release_table(snap)
    comps = [c for c in rt["comparisons"] if c["subject"] == "negative_share"]
    return {"period": {"start": start, "end": end, "prev_start": ps if trend_ok else None, "prev_end": pe if trend_ok else None},
            "headline": head, "prev_headline": prev, "fix_first": fixes[:3], "more_product_themes": max(0, len(fixes) - 3),
            "requests": asks[:2],
            "rising": rising, "risk": risk, "support": support, "min_size": min_size,
            "release": {"latest": comps[-1] if comps else None, "flagged": [c for c in rt["comparisons"] if c["flag"]],
                        "unknown": rt["unknown"]},
            "sample_size": snap["meta"]["n_reviews"], "app": snap["meta"].get("app", "this app").split(" (")[0]}


def check_brief(snap: dict, brief: dict) -> list:
    """Automatic checks. Returns a list of problems (empty means every check passed):
    every cited review exists, every quote is word for word from that review, no ranked theme is below the minimum."""
    rmap = {r["review_id"]: r for r in snap["reviews"]}
    problems = []
    for section in ("fix_first", "requests", "rising", "risk", "support"):
        for t in brief[section]:
            if t["reviews"] < brief["min_size"]:
                problems.append("%s: theme below the minimum size" % t["name"])
            for q in t["quotes"]:
                r = rmap.get(q["review_id"])
                if r is None:
                    problems.append("%s: cited review %s does not exist" % (t["name"], q["review_id"][:8]))
                    continue
                if " ".join(r["text"].split()).find(q["excerpt"].removesuffix(" …")) != 0:
                    problems.append("%s: quote from %s is not word for word" % (t["name"], q["review_id"][:8]))
                if (r["date"], r["score"]) != (q["date"], q["stars"]):
                    problems.append("%s: date or stars of %s do not match" % (t["name"], q["review_id"][:8]))
    return list(dict.fromkeys(problems))  # a theme shown in two sections reports each problem once


def _trend_words(t: dict) -> str:
    if t["prev_reviews"] is None:
        return ""
    if t["prev_reviews"] == 0:
        return " New this period."
    if t["reviews"] > t["prev_reviews"]:
        return " Up from %d last period." % t["prev_reviews"]
    if t["reviews"] < t["prev_reviews"]:
        return " Down from %d last period." % t["prev_reviews"]
    return " Same as last period (%d)." % t["prev_reviews"]


def render_markdown(brief: dict) -> str:
    p, h, ph = brief["period"], brief["headline"], brief["prev_headline"]
    L = ["## Weekly brief: %s to %s" % (_pretty(p["start"]), _pretty(p["end"])), ""]
    line = "I looked at **%d reviews**. The average rating is **%.2f**" % (h["reviews"], h["avg_rating"])
    line += (" (was %.2f)" % ph["avg_rating"]) if ph and ph["reviews"] else ""
    line += ", and **%.0f%%** are 1 to 2 stars" % (100 * h["negative_share"])
    line += (" (was %.0f%%)." % (100 * ph["negative_share"])) if ph and ph["reviews"] else "."
    L += [line, ""]

    def theme_block(i, t, claims=False):
        out = ["%s**%s** (%s): %d review%s, %.0f%% of reviews, %d critical or high.%s" %
               ("%d. " % i if i else "- ", t["name"], t["category"], t["reviews"], "" if t["reviews"] == 1 else "s",
                100 * t["share"], t["serious"], _trend_words(t))]
        if not claims and t["rating_lift"] > 0:
            out[0] += " If these reviews were as happy as the rest, the average rating would be about %.2f higher." % t["rating_lift"]
        if t["small_sample"]:
            out[0] += " *Small sample.*"
        for q in t["quotes"]:
            out.append("   - %d star, %s, %s, %s: \"%s\" (review %s)" %
                       (q["stars"], _pretty(q["date"]), _ver(q["version"]), q["severity"], q["excerpt"], _short_id(q["review_id"])))
        return out

    L.append("### What I'd fix first")
    if brief["fix_first"]:
        for i, t in enumerate(brief["fix_first"], 1):
            L += theme_block(i, t)
        if brief["more_product_themes"]:
            L.append("")
            L.append("%d more theme%s ranked below these, see the What to fix tab." %
                     (brief["more_product_themes"], "" if brief["more_product_themes"] == 1 else "s"))
    else:
        L.append("No product theme has %d or more reviews in this period." % brief["min_size"])
    if brief["requests"]:
        L += ["", "### What people are asking for"]
        for t in brief["requests"]:
            L += theme_block(0, t, claims=True)
    L.append("")
    L.append("### What is rising")
    if brief["rising"]:
        for t in brief["rising"]:
            L.append("- **%s**: %d reviews, %s" % (t["name"], t["reviews"], _trend_words(t).strip()))
    elif p["prev_start"] is None:
        L.append("There is no earlier period of the same length in this sample to compare with.")
    else:
        L.append("Nothing rose sharply.")
    if brief["risk"]:
        L += ["", "### Trust and risk: what reviewers claim, not verified facts"]
        for t in brief["risk"]:
            L += theme_block(0, t, claims=True)
    if brief["support"]:
        L += ["", "### Support"]
        for t in brief["support"]:
            L += theme_block(0, t, claims=True)
    L += ["", "### Releases"]
    rel = brief["release"]
    if rel["flagged"]:
        for c in rel["flagged"]:
            L.append("- **Flag:** %s went from %.0f%% to %.0f%% between %s and %s." %
                     (c["subject"], 100 * c["share_base"], 100 * c["share_new"], c["baseline"], c["version"]))
    elif rel["latest"]:
        c = rel["latest"]
        L.append("No version stands out as worse. Latest comparison, %s to %s: 1 to 2 star share %.0f%% to %.0f%%." %
                 (c["baseline"], c["version"], 100 * c["share_base"], 100 * c["share_new"]))
    else:
        L.append("Not enough reviews per version to compare.")
    u = rel["unknown"]
    L.append("%d reviews have no app version, so I left them out of release comparisons." % u["n"])
    L += ["", "*Based on a sample of %d reviews of %s. Themes with fewer than %d reviews are not ranked. "
          "Quotes are word for word.*" % (brief["sample_size"], brief["app"], brief["min_size"])]
    return "\n".join(L)
