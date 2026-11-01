"""Why model answers are rejected, and how often. Turns the checks in validate.py into a measurable rate.

An 'answer' is one model-produced label for one review (one attempt). It is rejected when it fails any check or
never arrives. Reasons are grouped into stable names so runs can be compared over time.
"""
from __future__ import annotations

import difflib
from collections import Counter

RULES = [  # (text that appears in the error message, stable reason name)
    ("quote not found", "quote_not_verbatim"),
    ("bad category", "invalid_category"),
    ("bad aspect sentiment", "invalid_sentiment"),
    ("bad overall_sentiment", "invalid_sentiment"),
    ("bad severity", "invalid_severity"),
    ("must have severity", "invalid_severity"),
    ("has severity 'none'", "invalid_severity"),
    ("aspect name must be", "aspect_name_length"),
    ("max is", "too_many_aspects"),
    ("usable=false but aspects", "usable_false_with_aspects"),
    ("usable must be", "invalid_structure"),
    ("aspects must be a list", "invalid_structure"),
    ("label is not an object", "invalid_structure"),
    ("bad impact flags", "missing_or_invalid_flags"),
    ("reviewId mismatch", "review_id_mismatch"),
    ("invalid JSON", "invalid_json"),
    ("refused", "refused"),
    ("could not produce valid JSON", "provider_token_cap"),
    ("request too large", "request_too_large"),
]


def classify_reason(message: str) -> str:
    for needle, name in RULES:
        if needle in message:
            return name
    return "other"


def quote_similarity(quote: str, text: str) -> float:
    """How closely the quote matches the best-fitting stretch of the review text (1.0 = identical)."""
    q, t = quote.lower(), text.lower()
    if not q or not t:
        return 0.0
    step, best = max(1, len(q) // 6), 0.0
    for i in range(0, max(1, len(t) - len(q) // 2), step):
        best = max(best, difflib.SequenceMatcher(None, q, t[i:i + len(q) + 10]).ratio())
    return best


def quote_kind(similarity: float) -> str:
    """altered: a small change (a dropped word or punctuation). paraphrased: reworded. invented: not in the review."""
    return "altered" if similarity >= 0.85 else ("paraphrased" if similarity >= 0.6 else "invented")


def summarize(events: list) -> dict:
    """events: dicts with kind 'check' (a label was checked), 'missing' (a label never arrived) or 'failure'
    (the whole answer failed, for n reviews)."""
    answers = rejected = aspects = quote_errors = 0
    by_reason, kinds = Counter(), Counter()
    for e in events:
        k = e["kind"]
        if k == "check":
            answers += 1
            aspects += e["aspects"]
            quote_errors += e["quote_errors"]
            kinds.update(e.get("quote_kinds", {}))
            if not e["ok"]:
                rejected += 1
                by_reason.update(e["reasons"])
        elif k == "missing":
            answers += 1
            rejected += 1
            by_reason["label_missing_from_batch"] += 1
        elif k == "failure":
            n = e.get("n", 1)
            answers += n
            rejected += n
            by_reason[e["reason"]] += n
    return {"answers_checked": answers, "answers_rejected": rejected,
            "rejection_rate": round(rejected / answers, 3) if answers else None,
            "by_reason": dict(by_reason.most_common()),
            "quotes_checked": aspects, "quotes_not_verbatim": quote_errors,
            "quotes_altered": kinds["altered"], "quotes_paraphrased": kinds["paraphrased"], "quotes_invented": kinds["invented"],
            "invented_quote_rate": round(kinds["invented"] / aspects, 4) if aspects else None}
