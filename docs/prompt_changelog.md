# Prompt changelog

Every prompt change with its measured effect on the dev split.

## extract_v2 (2026-10-31): uses labeling guide v1.1
- **Change:** severity rules rewritten (described impact decides severity, generic accusations are low, stated losses and delayed refunds are critical), tie-break "choose the lower level" removed.
- **Measured on:** the 35 reviews behind the 40 human-rated aspects (gpt-oss-120b on Groq, effort low, batches of 10). Output in `runs/v2_rated35/`.
- **Result against the human ratings (27 human-critical aspects):**

| | v1 | v2 |
|---|---|---|
| Critical recall | 11 of 27 (41%) | 10 of 27 (37%) |
| Exact severity agreement | 44% | 54% |
| Within one level | 97% | 77% |
| Aspect not found (category mismatch) | 4 | 5 |

- **Reading:** no real improvement on critical recall (difference of one case, within noise on 27). By category, payments improved (4 of 5 critical caught) while fraud claims got worse (1 of 7): the "generic accusation is low" rule was applied to reviews the human rated critical ("my money has gone"). Order-execution errors with money impact (forced square-off, stop loss not triggering) were still often rated high or medium.
- **Decision:** a prompt rewrite alone does not fix severity. Next approach: have the model extract observable impact flags and let code derive severity from the approved rubric.

## extract_v3 flags mode (2026-10-31): model reports impact flags, code derives severity
- **Change:** the model no longer outputs severity. It fills seven true/false flags per aspect (`docs/severity_rules.md`) and `src/voc/severity.py` derives the severity.
- **Measured on:** the same 35 reviews behind the 40 human-rated aspects, with gpt-oss-20b (the 120b model's daily Groq allowance was used up). Output in `runs/v3flags_20b_rated35/`. Not an exact like-for-like with the earlier 120b runs.
- **Result against the human ratings (27 human-critical aspects):**

| | v1 direct (120b) | v2 direct (120b) | v3 flags (20b) |
|---|---|---|---|
| Critical recall, strict (same category) | 11 of 27 (41%) | 10 of 27 (37%) | **17 of 27 (63%)** |
| Critical recall, review level (any aspect critical) | n/a | n/a | **24 of 27 (89%)** |
| Exact severity agreement | 44% | 54% | **78%** |
| Non-critical human rows called critical | 0 | 0 | 0 of 13 |

- **Strict misses (10):** 6 are category disagreements (the model used another category but marked the review critical), 4 are real severity misses: 3 fraud claims with no flag set (one says "money stuck" under a different aspect) and 1 wrong-Aadhaar data issue rated medium.
- **Rule gap found:** the guide calls account, security and data problems critical, but there is no flag for them. A `security_or_data_issue` flag is needed.
- **Caveats:** the rules were designed after seeing these same 40 ratings, so the numbers are optimistic. They need a check on ratings of other reviews. The sample is small.

## extract_v4 flags mode (2026-10-31): adds the `security_or_data_issue` flag
- **Change:** one new flag (security, privacy or data problems are critical, as the guide says).
- **Measured on:** the same 35 rated reviews, gpt-oss-20b. Output in `runs/v4flags_20b_rated35/`.

| | v3 flags | v4 flags |
|---|---|---|
| Critical recall, strict | 17 of 27 (63%) | **20 of 27 (74%)** |
| Critical recall, review level | 24 of 27 (89%) | **25 of 27 (93%)** |
| Exact severity agreement | 78% | 74% |
| Non-critical human rows called critical | 0 | **3** |

- **The 3 false criticals:** row 8 (a withdrawal that took a day; flagged `money_blocked`, human rated medium: a one-day wait is not a blocked withdrawal), and rows 23 and 40 (vague "you robbed me" claims flagged `money_lost`; human rated low). Rows 23 and 40 are the known weakness of the `money_lost` flag.
- **Decision:** no further change to prompt or rules until the human ratings of the fresh 30-review validation set (`data/golden/validation/`) are scored, so the validation stays an honest test. Candidate fixes to consider afterwards: define `money_blocked` as stuck or materially delayed, and require a concrete loss event for `money_lost`.
- Model run on the fresh set is done: `runs/v4flags_20b_val30/` (30 of 30 valid). Not yet scored, awaiting the human ratings.

## extract_v4 flags mode on the fresh validation set (2026-10-31)
- **Measured on:** 30 reviews the rules were not built on (not in the golden set, never rated before), rated by the product owner for the most serious problem in each review. gpt-oss-20b, flags mode, prompt v4. Ratings in `data/golden/human/severity_ratings_val30.csv`, output in `runs/v4flags_20b_val30/`.
- **Result (review level, model severity = highest aspect severity):**

| | |
|---|---|
| Critical recall | **7 of 7 (100%)** |
| Critical precision | **7 of 9 (78%)** |
| Exact agreement | 70% (21 of 30) |
| Within one level | 97% |
| Model 2+ levels above human / below human | 1 / 0 |

- **Caution:** only 7 human-critical cases, so recall has a wide margin of error (7 of 7 is also consistent with a true rate near 65%).
- **Where they differ:**
  - 4 reviews: model `none`, human `low` (feature requests and generic abuse). Not meaningful for ranking.
  - Row 11 (asks for alternatives to mobile OTP): `security_or_data_issue` fired, model critical, human low. The new flag over-triggers on mentions of login security. Needs "reports a security problem", not "mentions security".
  - Row 13 (sell shows executed but holding remains, no loss stated): `order_wrong`, model critical, human high. Ambiguous boundary: the human rated order failures critical when a loss was stated or implied.
  - Rows 1, 2, 20: one level apart (medium versus low, high). Row 20 is a month-long unresolved share transmission with no `core_action_blocked` flag.
- **Decision:** severity is good enough for v1. No further tuning on this set. Candidate fixes (security flag wording, `order_wrong` needing a loss) are recorded as known limits, to be revisited only with a new fresh validation set.

## Pipeline versus outside labeler (2026-11-01)
- **Setup:** the same 99 reviews (a random sample, first 9 of 42 chunks) labeled by ChatGPT (run by the product owner, impact flags) and by the pipeline (gpt-oss-20b, prompt v4, severity derived by code). 9 more reviews were not run because the free daily token limit was hit again. Output: `runs/pipeline_20b_agreement108/`.
- **All aspects:** usable agreement 75% (66 both usable, 8 both unusable, 23 pipeline-usable but ChatGPT-unusable, 2 the reverse). Aspect F1 0.60. Sentiment kappa 0.96. Severity weighted kappa 0.81. Review-level severity exact 86%, within one level 94%. Review-level critical: both 5, only ChatGPT 2, only pipeline 4 (kappa 0.59).
- **Main source of disagreement:** short praise such as "Easy to use" or "very nice good". ChatGPT calls it unusable, the pipeline labels it praise. The guide's wording on "bare rating words" is fuzzy at that boundary. Praise does not affect the fix list.
- **Problem aspects only (praise and other removed; a view chosen after seeing the above):** aspect F1 0.75, review-level category F1 0.76, sentiment kappa 0.88, severity weighted kappa 0.72. Both labelers found a problem in 36 of the 42 reviews either flagged (Jaccard 0.86). Weak categories: customer_support F1 0.44, login_kyc_account 0.40, crash_bug 0.00 (3 aspects).
- **Flag disagreements:** `core_action_blocked` (3 only ChatGPT, 3 only pipeline) and `event_described` are the least stable flags; money flags agree at 96% to 98%.
- **Cautions:** both labelers come from related model families, which may inflate agreement. No human verified either set. 30 of the 99 labeled reviews needed the slower one-at-a-time retry path.
- **Action candidate:** tighten the guide's "usable" wording for short praise.
