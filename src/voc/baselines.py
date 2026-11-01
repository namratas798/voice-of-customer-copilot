"""Non-AI baselines that emit labels in the same format, so the same eval applies."""
from __future__ import annotations

import re

RULES = [
    ("order_execution", r"stop.?loss|\border|execut|\bsell\b|\bbuy\b|\bmtf\b|trade"),
    ("payments_funds", r"withdraw|\bupi\b|\bbank\b|refund|deposit|payment|wallet|paisa|paise"),
    ("login_kyc_account", r"login|log in|\bkyc\b|\botp\b|\bpan\b|aadhaar|account (open|clos)"),
    ("crash_bug", r"crash|\bbug|freez|hang|not working|error|glitch"),
    ("performance", r"slow|lag\b|laggy|loading|delay"),
    ("charges_pricing", r"charge|brokerage|\bfees?\b|\bamc\b|\btax"),
    ("customer_support", r"support|customer care|no response|ticket"),
    ("fraud_money_loss_claim", r"fraud|scam|cheat|loot|\bfake|hack|chor"),
    ("feature_request", r"please add|should add|wish|add option|need option|add a "),
    ("ux_friction", r"\bui\b|interface|design|layout|confus|button|update"),
    ("praise", r"\b(good|best|great|nice|excellent|easy|smooth)\b"),
]


def _sentence(text: str, m) -> str:
    for part in re.split(r"(?<=[.!?\n])\s+", text):
        if m.group(0) in part.lower() or m.group(0) in part:
            return part.strip()
    return text


def _sent(score: int) -> str:
    return "negative" if score <= 2 else ("mixed" if score == 3 else "positive")


def _sev(score: int) -> str:
    return {1: "high", 2: "medium", 3: "low"}.get(score, "none")


def stars_label(review: dict) -> dict:
    n = len(review["content"].split())
    if n < 3:
        return {"reviewId": review["reviewId"], "usable": False, "overall_sentiment": _sent(review["score"]), "aspects": []}
    s = _sent(review["score"])
    sev = _sev(review["score"]) if s == "negative" else "none"
    return {"reviewId": review["reviewId"], "usable": True, "overall_sentiment": s,
            "aspects": [{"category": "other", "aspect": "overall review", "sentiment": s,
                         "severity": sev, "quote": review["content"]}]}


def keyword_label(review: dict) -> dict:
    text, score = review["content"], review["score"]
    aspects = []
    for cat, pat in RULES:
        m = re.search(pat, text, re.I)
        if not m or len(aspects) >= 3:
            continue
        s = "positive" if cat == "praise" else _sent(score)
        sev = _sev(score) if s == "negative" and cat not in ("other",) else "none"
        if s == "mixed":
            sev = "none"
        aspects.append({"category": cat, "aspect": cat.replace("_", " "), "sentiment": s,
                        "severity": sev, "quote": _sentence(text, m)})
    if len(text.split()) < 3 and not aspects:
        usable = False
    else:
        usable = True
    if usable and not aspects:
        aspects = [{"category": "other", "aspect": "unclassified", "sentiment": _sent(score),
                    "severity": "none", "quote": text}]
    return {"reviewId": review["reviewId"], "usable": usable, "overall_sentiment": _sent(score),
            "aspects": aspects if usable else []}


KINDS = {"stars": stars_label, "keywords": keyword_label}
