"""Rule checks that a JSON schema cannot express. Shared by labeling and production."""
from __future__ import annotations

import collections
import json

from .schema import CATEGORIES, MAX_ASPECTS, SENTIMENTS, SEVERITIES


def check_label(label: dict, text: str, max_aspect_words: int = 8) -> list:
    """Return a list of error strings for one label (empty list means valid)."""
    errs = []
    if not isinstance(label.get("usable"), bool):
        errs.append("usable must be true or false")
    if label.get("overall_sentiment") not in SENTIMENTS:
        errs.append("bad overall_sentiment %r" % (label.get("overall_sentiment"),))
    aspects = label.get("aspects")
    if not isinstance(aspects, list):
        return errs + ["aspects must be a list"]
    if len(aspects) > MAX_ASPECTS:
        errs.append("%d aspects, max is %d" % (len(aspects), MAX_ASPECTS))
    if label.get("usable") is False and aspects:
        errs.append("usable=false but aspects not empty")
    for a in aspects:
        if a.get("category") not in CATEGORIES:
            errs.append("bad category %r" % (a.get("category"),))
        if a.get("sentiment") not in SENTIMENTS:
            errs.append("bad aspect sentiment %r" % (a.get("sentiment"),))
        sev = a.get("severity")
        if sev not in SEVERITIES:
            errs.append("bad severity %r" % (sev,))
        if a.get("sentiment") in ("positive", "neutral") and sev != "none":
            errs.append("positive/neutral aspect must have severity 'none'")
        if a.get("sentiment") == "negative" and sev == "none" and a.get("category") != "other":
            errs.append("negative aspect %r has severity 'none'" % (a.get("aspect"),))
        name = a.get("aspect")
        if not name or not (1 <= len(name.split()) <= max_aspect_words):
            errs.append("aspect name must be 1 to %d words" % max_aspect_words)
        q = a.get("quote")
        if not q or q not in text:
            errs.append("quote not found verbatim in review: %r" % (q,))
    return errs


def validate_files(inputs_path: str, labels_path: str):
    """Validate a labels JSONL against its input JSONL. Returns (n_inputs, n_labeled, errors)."""
    inputs = {}
    for line in open(inputs_path):
        r = json.loads(line)
        inputs[r["reviewId"]] = r["content"]
    errors, seen = [], collections.Counter()
    for n, line in enumerate(open(labels_path), 1):
        line = line.strip()
        if not line:
            continue
        try:
            lab = json.loads(line)
        except json.JSONDecodeError:
            errors.append("line %d: invalid JSON" % n)
            continue
        rid = lab.get("reviewId")
        seen[rid] += 1
        if rid not in inputs:
            errors.append("line %d: unknown reviewId %s" % (n, rid))
            continue
        for e in check_label(lab, inputs[rid]):
            errors.append("%s: %s" % (rid[:8], e))
    missing = set(inputs) - set(seen)
    dups = [k for k, v in seen.items() if v > 1]
    if missing:
        errors.append("%d reviews not labeled" % len(missing))
    if dups:
        errors.append("%d reviewIds labeled more than once" % len(dups))
    return len(inputs), len(seen), errors
