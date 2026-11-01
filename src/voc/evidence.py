"""Measured results shown on the app's "How reliable is this?" page. Each figure comes from a script in scripts/."""

EVIDENCE = {
    "as_of": "2026-10-31",
    "severity_fresh_validation": {
        "what": "30 reviews the rules were not built on, rated by the product owner for the most serious problem in each review",
        "model": "gpt-oss-20b, impact flags with severity derived by code (prompt v4)",
        "critical_recall": "7 of 7", "critical_precision": "7 of 9 (78%)", "exact_agreement": "70%", "within_one_level": "97%",
        "caution": "Only 7 critical cases, so recall has a wide margin of error.",
    },
    "severity_before_after": [
        {"approach": "Model gives severity directly (prompt v1)", "critical_recall": "41% (11 of 27)", "note": "tested on the 27 human-rated critical aspects"},
        {"approach": "Model reports facts, code derives severity", "critical_recall": "63% strict, 89% to 93% at review level",
         "note": "same 27 aspects; rules were designed after seeing them, so optimistic"},
    ],
    "extraction_vs_ai_labels": {
        "what": "200 dev reviews, first prompt, gpt-oss-120b against labels from a second AI labeler (not human-verified)",
        "aspect_precision": 0.83, "aspect_recall": 0.86, "aspect_f1": 0.85, "category_macro_f1": 0.83, "sentiment_kappa": 0.97, "keyword_baseline_aspect_f1": 0.55,
    },
    "labeler_agreement": {
        "what": "99 reviews labeled independently by ChatGPT (run by the product owner) and by the pipeline (gpt-oss-20b, prompt v4). Neither is treated as truth.",
        "usable_agreement": "75%", "sentiment_kappa": 0.96, "severity_kappa": 0.81,
        "problem_precision": 0.83, "problem_recall": 0.68, "problem_aspect_f1": 0.75,
        "critical": "5 reviews both called critical, 2 only ChatGPT, 4 only the pipeline",
        "caution": "Most disagreement is short praise such as 'Easy to use' (usable or not). Problem-only agreement was chosen as a view after seeing this. Both labelers are from related model families, which may inflate agreement. 9 of 108 reviews were not run (free daily limit).",
    },
    "themes": "Grouping by word matching plus an AI merge step. The author judged 7 of 10 ranked themes clearly coherent and 3 slightly broad. A formal human check (bar: 85%) is still open.",
    "release_comparison": "Only versions with at least 30 reviews are compared. In this sample three comparisons qualified and none showed a significant rise.",
    "open_items": [
        "No human has verified the category and aspect labels, only severity on 70 cases.",
        "Shares are from a random sample of reviews that pass the gate, not every review.",
    ],
}
