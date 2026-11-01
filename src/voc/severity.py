"""Deterministic severity from observable impact flags. Rules: docs/severity_rules.md.

The model reports facts about each aspect (did money get lost, is a core action blocked, ...).
This code, not the model, decides the severity, so the policy is visible and adjustable.
"""
from __future__ import annotations

import copy

from .schema import IMPACT_FLAGS


def derive_severity(aspect: dict) -> str:
    """aspect needs: category, sentiment, impact (dict of IMPACT_FLAGS booleans)."""
    if aspect["sentiment"] in ("positive", "neutral") or aspect["category"] in ("praise", "other"):
        return "none"
    f = aspect["impact"]
    if (f["money_lost"] or f["money_blocked"] or f["loss_amount_stated"] or f["order_wrong"]
            or f["security_or_data_issue"]):
        return "critical"
    if aspect["category"] == "feature_request":
        return "low"
    if f["core_action_blocked"]:
        return "medium" if f["workaround_mentioned"] else "high"
    if f["event_described"]:
        return "medium"
    return "low"


def finalize_label(label: dict) -> dict:
    """Return a copy of the label with a derived `severity` on every aspect (impact kept for audit).
    Raises ValueError if any impact flag is missing or not a boolean."""
    out = copy.deepcopy(label)
    for a in out.get("aspects", []):
        imp = a.get("impact")
        if not isinstance(imp, dict) or any(not isinstance(imp.get(k), bool) for k in IMPACT_FLAGS):
            raise ValueError("impact flags missing or not boolean")
        a["severity"] = derive_severity(a)
    return out
