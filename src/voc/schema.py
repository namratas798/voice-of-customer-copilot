"""Single source of truth for labels. Matches docs/labeling_guide.md (v1.0)."""

CATEGORIES = [
    "order_execution", "payments_funds", "login_kyc_account", "crash_bug",
    "performance", "ux_friction", "feature_request", "charges_pricing",
    "customer_support", "fraud_money_loss_claim", "praise", "other",
]
NON_PRODUCT = {"customer_support", "fraud_money_loss_claim", "praise", "other"}
SENTIMENTS = ["positive", "negative", "mixed", "neutral"]
SEVERITIES = ["none", "low", "medium", "high", "critical"]  # ordinal, low to high
SEV_WEIGHT = {"critical": 8, "high": 4, "medium": 2, "low": 1, "none": 0}
MAX_ASPECTS = 3

IMPACT_FLAGS = [
    "event_described", "money_lost", "money_blocked", "loss_amount_stated",
    "order_wrong", "core_action_blocked", "workaround_mentioned", "security_or_data_issue",
]

EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reviewId", "usable", "overall_sentiment", "aspects"],
    "properties": {
        "reviewId": {"type": "string"},
        "usable": {"type": "boolean"},
        "overall_sentiment": {"enum": SENTIMENTS},
        "aspects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "aspect", "sentiment", "severity", "quote"],
                "properties": {
                    "category": {"enum": CATEGORIES},
                    "aspect": {"type": "string"},
                    "sentiment": {"enum": SENTIMENTS},
                    "severity": {"enum": SEVERITIES},
                    "quote": {"type": "string"},
                },
            },
        },
    },
}


def _flags_schema():
    """Same label, but each aspect carries observable impact flags instead of a severity.
    Severity is derived afterwards by code (src/voc/severity.py)."""
    import copy
    s = copy.deepcopy(EXTRACTION_SCHEMA)
    item = s["properties"]["aspects"]["items"]
    del item["properties"]["severity"]
    item["required"] = [r for r in item["required"] if r != "severity"] + ["impact"]
    item["properties"]["impact"] = {
        "type": "object", "additionalProperties": False, "required": IMPACT_FLAGS,
        "properties": {f: {"type": "boolean"} for f in IMPACT_FLAGS},
    }
    return s


FLAGS_EXTRACTION_SCHEMA = _flags_schema()
