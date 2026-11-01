# PRD: Voice of Customer Copilot (v0.1 draft)

Status: draft for review. Items marked **[proposed]** are my defaults and need your decision. Items marked **[provisional]** are numbers to be recalibrated after the first labeling pass.

## 1. Summary

A copilot that turns app-store reviews into prioritized, evidence-backed decisions for a product manager. v1 targets one app (Groww, Google Play, English plus Hinglish) and one persona.

The product's value is trust, not summarization. Every insight shows its evidence, every number comes from code, and the system says "insufficient evidence" when the data is thin.

## 2. Problem

Maya, a PM on a consumer fintech app, gets about 130 reviews a day. She can't read them all. Her current process is skimming recent 1★ reviews on Monday, and she can't tell which complaints are real, growing and worth fixing, or defend that choice to engineering and leadership.

Data reality (Groww, 36 days, 4,600 reviews):
- 78% are 5★, 71% are 3 words or fewer, and the median is 2 words.
- Only about 336 reviews (about 9 a day) are substantive 1–2★ complaints. This is the real signal.
- About 6% of reviews are Hinglish or Devanagari (keyword heuristic, likely undercounted).
- 7% have no app version, and those are about 33% negative against 5–11% for versions with one.
- Developer replies are 13 boilerplate templates and carry no information.

## 3. Users

**Primary: Maya, product manager** (squad owner for trading, payments or onboarding). Ships every 1–2 weeks. Time-poor, skeptical of AI summaries, needs evidence she can forward.

**Secondary (v2):** engineering lead (bug triage), support ops, leadership.

## 4. Goals and non-goals

### Goals
1. Maya reaches a prioritized fix list in under 15 minutes. Baseline to measure: roughly 2 hours of manual reading.
2. Every claim in the output traces to verbatim reviews.
3. Detect a release-related regression within days, not weeks. Measured by backtest.
4. Demonstrate disciplined AI use: AI only where it beats a non-AI baseline, with measured evidence.

### Non-goals (v1)
- Competitor tracking, churn prediction, auto-replying to reviews.
- Multiple review sources (App Store, Reddit, support tickets).
- Private analytics (funnels, crash logs).
- Real-time alerting. v1 is a weekly or on-demand batch.
- Multilingual support beyond English and Hinglish.

## 5. Decisions the product supports

| # | Maya's decision | Output | Logic |
|---|---|---|---|
| D1 | What should we fix this sprint? | Ranked theme list | AI extracts and clusters, code ranks |
| D2 | Did the last release break something? | Version-over-version regression flags | Code detects, AI explains cause |
| D3 | Bug, UX problem or feature request? Who owns it? | Category and owner per theme | AI classifies |
| D4 | What do users ask for that we don't have? | Feature-request themes with demand counts | AI |
| D5 | What do I tell leadership? | Weekly brief with evidence and confidence | AI writes, code supplies numbers |
| D6 | Why is X happening? (ad hoc) | Chat with tool access to themes, quotes and time ranges | Agent |

D1 and D2 carry the value and are built first. D6 is built last.

## 6. Solution overview

```
Ingest -> Clean -> Gate -> [AI] Per-review extraction -> Embed + cluster -> [AI] Theme naming
       -> Deterministic aggregation (counts, trends, segments, rating drag, regression tests)
       -> [AI] Brief writer (cites only retrieved quotes) -> UI + chat agent
```

### 6.1 AI vs deterministic split

| Step | Approach | Why |
|---|---|---|
| Ingest, dedupe, strip identity fields | Code | No ambiguity. Names and avatars are removed. |
| Developer replies | Code: excluded from all model inputs | Boilerplate and sentiment-keyed, so they leak |
| Substantive gate | Code (rules: length, keywords) | About 70% of rows need no LLM. Has its own error metric. |
| Language and script detection | Code | Cheap and sufficient for routing |
| Per-review extraction (category, aspects, sentiment, severity, quote) | **AI** | Free text, mixed sentiment, Hinglish, sarcasm |
| Grouping aspects into themes | Embeddings plus clustering **[proposed]** | Stable and cheap. An LLM only names the clusters. |
| Theme naming and category assignment | **AI** | Needs language understanding |
| Counts, shares, trends, rankings, rating drag | Code | LLMs must never compute numbers |
| Regression detection | Code (statistical test with minimum sample) | Reproducible and explainable |
| Brief writing | **AI**, constrained | Narrative from verified inputs only |
| Chat | **AI agent** with tools | Open-ended questions |

### 6.2 Per-review output schema
Defined in `docs/labeling_guide.md` and enforced by `scripts/validate_labels.py`. The production extractor uses the same schema and the same validator, so labeling and production share one definition.

Fields: `usable`, `overall_sentiment`, up to 3 aspects (each: `category`, `aspect`, `sentiment`, `severity`, `quote`).

Categories (12): order_execution, payments_funds, login_kyc_account, crash_bug, performance, ux_friction, feature_request, charges_pricing, customer_support, fraud_money_loss_claim, praise, other. Four are non-product categories (customer_support, fraud_money_loss_claim, praise, other) and never enter the fix list.

## 7. Functional requirements

### FR1 Ingestion and gate
- Pull Play Store reviews for the app weekly and on demand, and store them locally.
- Remove userName, userImage and developer reply text before any further processing.
- Keep reviews with missing app version in an explicit "unknown version" bucket, never drop them.
- The gate marks a review as a candidate for AI extraction using explicit rules. Requirement: false-negative rate on actionable reviews of at most 2% on the golden set **[provisional]**.

### FR2 Extraction
- Output must pass schema validation. Invalid output is retried, then flagged, never silently kept.
- Each aspect must include a quote that exists verbatim in the review.

### FR3 Themes
- Aspects are grouped into themes. Each theme has a name, a category, a count, and 3 or more representative quotes.
- A theme needs at least **5 reviews [decided]** to appear in a ranked list. Smaller groups show under "emerging, low evidence".
- Users can rename, merge, split or hide a theme, and those edits are saved as feedback data.

### FR4 Ranking (D1)
Priority score per theme and window, computed in code:
`score = sum(severity_weight per review) x trend_multiplier`
with weights critical 8, high 4, medium 2, low 1 **[decided as starting values, adjustable]**. Rating drag is reported separately: the average-rating lift if the theme's reviews had the average rating of all non-theme reviews.
The formula and weights are visible in the UI. Maya can change the weights.

### FR5 Regression detection (D2)
- Compare negative-review share and theme shares between consecutive versions and consecutive weeks.
- Flag only when both a minimum sample (**n of at least 30 per window [decided]**) and a statistical threshold are met. Otherwise display "insufficient evidence".
- Always show the "unknown version" bucket next to the versioned comparison.

### FR6 Brief (D5)
- The brief is generated from structured, code-computed inputs plus retrieved quotes.
- Every sentence with a claim carries citations to review IDs. A post-check removes or flags any claim without a valid citation.
- Every number in the brief must match the code output (automated check).
- Each theme shows sample size and a "directional only, reviews are a vocal minority" note.

### FR7 Chat agent (D6)
Tools (all read-only): `get_top_themes(window, filters)`, `get_theme_detail(theme_id)`, `search_reviews(query, filters)`, `compare_windows(a, b)`, `get_version_stats(version)`.
The agent may not state a number it did not receive from a tool. It answers "I don't have evidence for that" when the tools return nothing relevant.

### FR8 Safety and tone (fintech)
- Money-loss, fraud and legal claims are always attributed ("a reviewer claims…") and never stated as fact.
- Fraud and money-loss claim themes are routed to a separate trust-and-risk view, not mixed with the product fix list.
- No personal identifiers in any output.

## 8. UX outline

1. **This week's brief:** top themes ranked, regression flags, what's new, with evidence expanders.
2. **Theme detail:** definition, category and owner, trend, version split, quotes, severity mix.
3. **Releases:** version-by-version health, including the unknown bucket.
4. **Ask:** chat with the agent.
5. **Review labels:** feedback controls (rename, merge, hide) feeding the eval set.

Form factor **[decided]**: Python pipeline with a lightweight web UI (Streamlit). Chosen for build speed and demo-ability.

Demo data **[decided]**: the public portfolio demo uses a frozen snapshot of the collected data, so evals are reproducible and there is no ongoing public scraping. Live collection stays a private tool.

### 8.1 Performance and demo plan **[decided 2026-10-31]**

The analysis is a weekly offline batch. The PM reads saved results, so most of the product must respond instantly. On Groq's free tier a 200-review batch takes about 20 minutes (8,000 tokens a minute limit), which is a free-tier limit and not a product requirement. Measure and report the paid-tier time before claiming a number.

| Feature | Mode | Target latency |
|---|---|---|
| Weekly brief, ranked themes, release health, theme drill-down | Precomputed | under 1 s |
| Paste-a-review live demo (single review) | One live model call | under 5 s |
| Chat agent | Live calls with tools, or preloaded example questions | under 15 s |
| Evaluation results and model comparison | Static | under 1 s |

Portfolio package: frozen snapshot demo with precomputed results, one live feature (paste-a-review), a 2-minute walkthrough video as a backup, and a case study page covering baselines, model comparison and the severity story. Live features are rate-limited and never expose an API key. The demo states the snapshot date.

## 9. Model strategy **[proposed, to be confirmed by benchmark]**

| Task | Starting choice | Why |
|---|---|---|
| Per-review extraction (high volume) | Small, cheap tier with structured output and batching | Narrow task. The benchmark decides. |
| Embeddings for clustering | Multilingual embedding model | Hinglish and Devanagari |
| Theme naming, brief, chat | Mid tier | Needs quality but low volume |
| Eval judge | Stronger tier, used sparingly | Judge quality matters more than cost |

Rule: the chosen model is the cheapest one that clears the quality bar on the held-out test set. We publish quality, cost per 1,000 reviews, and latency for at least 3 options. The labeling model must come from a different family than the evaluated one, to avoid self-preference.

## 10. Evaluation criteria (PM checklist)

This is what I check, in order, before I trust the flow or show it to anyone. Each row says what to check, how, the bar, and where we are. The bars were set before the results were seen and stay provisional until the first test-set run.

Status key: ✅ measured | 🟡 partly measured or weak evidence | ⬜ not done yet | 🔒 feature not built yet

### 10.1 Ground rules
1. Check each stage on its own. A bad insight can come from the gate, the reading step, the severity rules, the themes or the ranking. One end-to-end number hides which.
2. Two kinds of truth: my own ratings (for what matters most) and a second labeler (for agreement). Agreement with an AI is never called accuracy.
3. Tune on the dev set, score the test set once. Anything tuned on a set looks better on that set than it is.
4. Always show the number of cases. Under about 30 cases, show the count and a range, not just a percentage.
5. Always compare with a simple baseline (stars only, keyword rules).
6. Report by slice: Hinglish versus English, short versus long reviews, each category.
7. Log every change to a prompt, rule or scoring method with the reason and the result (`docs/prompt_changelog.md`, `docs/eval_changelog.md`, `docs/guide_changelog.md`).

### 10.2 The flow, and who checks what

| # | Stage | Done by | Checked by |
|---|---|---|---|
| 1 | Collect and clean | code | tests and a privacy scan |
| 2 | Gate (drop reviews with no signal) | code rules | missed-signal test |
| 3 | Read each review (categories, problems, sentiment) | AI model | my labels, a second labeler, baselines |
| 4 | Severity | AI reports facts, code decides | my ratings |
| 5 | Themes | word matching plus an AI merge step | my coherence check |
| 6 | Ranking | code | my own top 5 |
| 7 | Release comparison | code (statistics) | synthetic tests, no-change tests |
| 8 | Weekly brief | code, from computed numbers and real quotes | automated checks and PM ratings |
| 9 | Chat agent with tools 🔒 | AI plus read-only tools | tool-call test set |
| 10 | App | code | PM task test |
| 11 | Live "try a review" | the same reader | latency and failure tests |

### 10.3 Checklist by component

**A. Collection and privacy**

| Check | How | Bar | Status |
|---|---|---|---|
| No personal data kept (names, photos, developer replies) | scan the stored data and the app snapshot, including emails and phone numbers | 0 found | ✅ fields dropped at ingest. `scripts/privacy_scan.py` found no emails, phone numbers, PAN, Aadhaar-like numbers or UPI ids in the 4,600 reviews, and one 9-digit number in a raw file only (not in the app data) |
| Duplicates, empty reviews, missing versions handled | automated tests | pass | ✅ |
| Missing version never silently dropped | shown as its own group | shown | ✅ |
| Only public data, within the store's terms | read the terms before any public demo | written down | ⬜ |

**B. Gate**

| Check | How | Bar | Status |
|---|---|---|---|
| Missed signals: actionable reviews the gate skips | label at least 150 randomly chosen skipped reviews and count the actionable ones | at most 2% (zero misses in 150 proves it at 95% confidence) | 🟡 0 of 129 missed on dev, but only about 25 skipped reviews were in that sample, so it can't prove the bar |
| Noise let through | share of passed reviews that are unusable | report | ⬜ |
| Real pass rate | passed / all reviews | report | ✅ 23% (1,078 of 4,600) |
| Every skip has a reason | logged per review | yes | ✅ |
| Honest value claim | it saves noise and time, not meaningful money at this volume | stated that way | ✅ |

**C. Reading each review (extraction)**

| Check | How | Bar | Status |
|---|---|---|---|
| Valid answers without a retry | share passing the schema and rules in the first batch call | 95% or more | 🟡 78 of 99 in the last run, the rest recovered one at a time, none failed |
| Every quote is real text | quote found word for word in the review | 100% (enforced) | ✅ |
| Failures never silently dropped | status for every review (ok, failed, refused, not run) | 0 silent drops | ✅ |
| Category accuracy (macro F1) | against labels, by category | 0.80 or more | 🟡 0.83 against AI labels (200 dev reviews, first prompt), not human-verified |
| Problem finding (F1) | same | 0.75 or more | 🟡 0.85 against AI labels, 0.75 against the second labeler on problems only |
| Sentiment (kappa) | same | 0.70 or more | ✅ 0.97 against AI labels, 0.96 between labelers |
| Usable versus not | precision and recall | report | 🟡 0.91 and 0.97 against AI labels, only 75% agreement between labelers (short praise) |
| Human check of categories and problems | I label at least 60 reviews blind, then compare | kappa and per-category rates reported | ⬜ postponed, the biggest credibility gap |
| Beats simple baselines | against stars only and keyword rules | clear lift | ✅ F1 0.85 versus 0.55 (keywords) and 0.04 (stars) |
| Works across slices | Hinglish and English, short and long, each category | no slice far below the rest | 🟡 harness built, not run for the current prompt |
| Stable | run the same reviews twice, share of labels unchanged | 90% or more | ⬜ |
| Prompt changes are safe | every change re-run on a frozen dev set and compared | no drop | 🟡 done by hand and logged, not automated |
| Instructions hidden in a review do not change behavior | 10 test reviews containing "ignore the above"-style text | 0 changes | ⬜ |
| Error analysis written down | read the failures and name the patterns | written | 🟡 partly (short praise, support and login categories) |

**D. Severity**

| Check | How | Bar | Status |
|---|---|---|---|
| Critical issues caught | against my ratings on reviews not used to design the rules | 90% or more | 🟡 7 of 7 on 30 fresh reviews, but only 7 critical cases, so the margin is wide |
| Critical calls that are right | same | 70% or more | ✅ 78% (7 of 9) |
| Never badly wrong | cases two or more levels off | none below, few above | ✅ 0 below, 1 above |
| Agreement (weighted kappa) | against humans or the second labeler | 0.60 or more | ✅ 0.79 against AI labels, 0.81 between labelers |
| Larger fresh test | at least 15 human-rated critical cases | done | ⬜ |
| Flag accuracy | each flag against my ratings | report | ⬜ labelers disagree most on `core_action_blocked` and `event_described` |
| Rules readable and owned by the PM | `docs/severity_rules.md` | present | ✅ |

**E. Themes**

| Check | How | Bar | Status |
|---|---|---|---|
| Coherence | I mark each ranked theme: one problem, one owner? | 85% or more | ⬜ formal check pending, my own read was 7 of 10 |
| Coverage | share of problem reviews inside a ranked theme | report, aim for 60%+ | 🟡 56% |
| Over-merging and under-merging | read the example phrases of the top themes and count mixed ones | few | 🟡 3 of 10 slightly broad |
| Merge step is safe | invented group ids, forgotten groups | 0 invented | ✅ 0 invented, 1 forgotten (kept on its own) |
| Themes stay stable week to week | same IDs on re-runs | stable | 🔒 |
| Reproducible | same input gives the same themes | yes | 🟡 cached, a fresh re-run was not compared |

**F. Ranking**

| Check | How | Bar | Status |
|---|---|---|---|
| Formulas correct | unit tests for weights, trend, rating lift | pass | ✅ |
| I agree with the order | I pick my top 5 blind, compare with the tool's top 5 | 4 of 5 overlap | ⬜ |
| The score is understandable | 3 PMs explain "priority score" in their own words | at least 2 of 3 | ⬜ first feedback said it was unclear, fixed |
| Not misleading when data is thin | minimum reviews, "emerging" label | enforced | ✅ |
| Sample bias stated | shares come from a random sample | stated | ✅ |

**G. Release comparison**

| Check | How | Bar | Status |
|---|---|---|---|
| Statistics correct | known test values | pass | ✅ |
| No false alarms | shuffle which version each real review belongs to, so any difference is chance | 0 flags | ✅ 18 of 2,000 shuffles (0.9%) flagged on the 1 to 2 star share, 0 of 150 when all 95 themes are included (`docs/regression_checks.md`) |
| Catches a real change | inject a known spike | flagged | 🟡 only big changes: with 80 reviews per version a doubling (25% to 50% of reviews at 1 to 2 stars) is flagged 74% of the time, 150 reviews 96%. A 1.6x rise is flagged 23% (150 reviews: 57%). One theme going from 5% to 30%: 62%. So "no flag" does not mean "no problem" |
| Real backtest | a known bad release in the history | flagged within days | ⬜ needs more history |
| Honest when thin | 30-review minimum | enforced | ✅ 3 comparisons qualified, 0 flags |

**H. Weekly brief**

| Check | How | Bar | Status |
|---|---|---|---|
| Every claim cites real reviews | automated: the ids exist and contain the claim | 100% | ✅ checked on every brief (`check_brief`): cited reviews exist, date and stars match, quote is word for word from that review. A failing brief shows an error instead of text |
| Every number comes from code | no digits outside placeholders | 100% | ✅ the brief is written by code from computed values, no model writes any sentence in v1 |
| Quotes are word for word | substring check | 100% | ✅ part of the same automatic check |
| Fraud and money claims attributed ("a reviewer claims") | automated check plus a sample read | 0 violations | ✅ they sit in their own section headed "what reviewers claim, not verified facts", covered by a test |
| Sample-size caveat on thin themes | automated | 100% | ✅ every theme under 30 reviews is marked "Small sample" |
| A PM would act on it | 3 to 5 PMs rate 1 to 5 | average 4 or more | ⬜ built, not yet rated |
| Readable in 2 minutes | timed | 2 minutes or less | ⬜ not timed |

**I. Chat agent and tool calls 🔒**

| Check | How | Bar | Status |
|---|---|---|---|
| Picks the right tool | 30 test questions with the expected tool | 90% or more | 🔒 |
| Right arguments | dates, filters, theme id | 90% or more | 🔒 |
| Never states a number a tool did not return | trace every number to a tool result | 100% | 🔒 |
| Says "I don't have evidence" when it should | questions with no answer in the data | 90% or more | 🔒 |
| Read-only | try to make it write | impossible | 🔒 |
| Tool errors handled | simulate failures | graceful message | 🔒 |
| Call limit respected | no more than 8 calls per question | 100% | 🔒 |
| Resists instructions hidden in reviews | review text such as "ignore previous instructions" | no change in behavior | 🔒 |
| Latency and cost per question | measure | 15 seconds or less, cost reported | 🔒 |

**J. App and PM usability**

| Check | How | Bar | Status |
|---|---|---|---|
| Time to a prioritized fix list | stopwatch with a PM against the manual way | under 15 minutes against about 2 hours | ⬜ |
| Understandable without me | 3 PMs think aloud on the first screen, count their questions | 2 or fewer each | 🟡 first feedback round done and fixed (priority, severity levels, facts) |
| Every number explained | hover text on every metric | yes | ✅ |
| Evidence one click away | every theme opens to real reviews | yes | ✅ |
| Failure states are friendly | live demo busy, no key | plain message | ✅ |
| Load time of precomputed pages | timed | under 1 second | 🟡 feels instant, not timed |

**K. Safety, legal and privacy**

| Check | How | Bar | Status |
|---|---|---|---|
| Fraud and money claims never stated as fact | scan outputs, warning shown on the page | 0 | 🟡 app and brief label them as claims by design, no automated scan of free text |
| No personal data in any output | scan | 0 | ✅ for stored data |
| Secrets never exposed | key file never committed, key only on the server | pass | ✅ automated scan finds no keys in the project, the key file is owner-only, and `.gitignore` covers the key file, raw data and caches. Rerun right before publishing |
| Model provider terms for free tiers | read and note the data-use terms | noted | ⬜ |
| Who labeled what is recorded | source on every label | yes | ✅ |

**L. Latency**

| Step | Target | Status |
|---|---|---|
| Precomputed pages | under 1 s | 🟡 feels instant |
| Paste-a-review (one review, one call) | under 5 s (95th percentile) | ⬜ not timed |
| Reading 200 reviews | free tier: report it, paid: under 3 minutes | 🟡 about 20 minutes on the free tier (limit-bound), paid ⬜ |
| Chat question | under 15 s | 🔒 |
| Weekly refresh | finishes overnight | 🟡 |

Per-call time and tokens are now saved for every real model call (`data/llm_cache.db.calls.jsonl`, report with `scripts/latency_report.py`). The log starts with the next model call, so there are no real latency numbers yet.

**M. Cost**

| Check | How | Bar | Status |
|---|---|---|---|
| Tokens per review | measure from run logs | report | ✅ about 1,090 (about 820 in, 270 out), 1,420 with retries |
| Cost per 1,000 reviews by model | benchmark table | report | 🟡 table built from measured tokens (`docs/cost_latency.md`): about $0.22 per 1,000 reviews on the cheapest paid models, $2.2 on mid-tier, $4.3 on Sonnet-class, $8.6 on Opus-class, $0 on the free tier. Quality across models not compared yet |
| Monthly cost at today's volume | about 30 reviews a day pass the gate | report | ✅ about $0.19 a month on the cheapest paid models, about $3.9 on Sonnet-class |
| Cost at 10 times and 100 times the volume | projection | report | ✅ in `docs/cost_latency.md` (cheapest paid: $1.94 and $19.39 a month) |
| Cost of the evaluation itself | tokens used for tests | report | ⬜ |
| Free-tier cap handled | stops cleanly, resumes from the cache | yes | ✅ |

**N. Model benchmark**
Run the same frozen reviews through 2 or 3 models and compare quality by stage against cost and speed. Choose the cheapest model that clears the bars, per slice. 🟡 Two free models tried (gpt-oss-120b and gpt-oss-20b). No paid model tested.

**O. Reliability and operations**

| Check | How | Bar | Status |
|---|---|---|---|
| Failures are visible | failed, refused and not-run statuses | no silent drops | ✅ |
| Reruns do not repeat work | cache | yes | ✅ |
| Fallback rate (batch to one at a time) | from run logs | report | 🟡 21 of 99 in the last run |
| Drift | label mix and vocabulary compared week to week | flagged | ⬜ |
| Automated tests | run on every change | pass | ✅ 64 tests |

**P. Bias and representativeness**

| Check | How | Bar | Status |
|---|---|---|---|
| Reviews are a vocal minority | stated, no population claims | stated | ✅ |
| Sampling method written down | random from gate-passing, golden set excluded | written | ✅ |
| Numbers from the stratified golden set never shown as real shares | stated | stated | ✅ |
| Hinglish coverage and quality | by slice | report | ⬜ |

**Q. Hallucination checks (every place a model is used)**

| Where a model is used | How it could hallucinate | How we catch it | Status |
|---|---|---|---|
| Reading a review: the quote | Invents or changes a quote | The quote must appear word for word in that review, otherwise the answer is rejected, retried, escalated or marked failed | ✅ enforced on every answer, and now measured: every run saves why each answer was rejected (`rejections.jsonl`, summary in `run.json`). First look, a partial replay of 84 saved answers: 4 of 67 quotes were not word for word. 3 were tiny changes (a dropped word or punctuation) and 1 was invented, a sentence that is not in the review (1.5%). All were caught and redone |
| Reading a review: the label | Picks a category or problem the text does not support, even with a real quote | Not caught automatically. Compare with a second labeler, human check of categories, read the disagreements | 🟡 problems-only agreement F1 0.75, human check ⬜ |
| The true/false facts behind severity | Says "money lost" or "order wrong" when the text does not | Two labelers disagreeing on a flag marks it as suspect. Severity is checked against my ratings: 2 of 9 critical calls were wrong | 🟡 flag disagreements not yet read one by one |
| A batch of reviews in one call | Mixes up reviews, skips one, or merges two | Every label carries a review id that must match, quotes must come from that review's own text, a missing label is redone | ✅ |
| Invalid values | Makes up a category or severity | Fixed lists in the answer format and again in code | ✅ |
| Empty or meaningless input | Invents a problem from nothing | Negative controls: gibberish, emoji-only and near-empty reviews should come back "not usable" | ⬜ a few seen in passing, not tested as a set |
| Reviews that contain instructions | Follows the instruction inside the review | 10 test reviews with "ignore the above" style text | ⬜ |
| Theme merge | Invents a group, or merges different problems | Invented ids are dropped (0 in the run), merging never crosses a category. Whether merges make sense is my coherence check | ✅ safety rules, ⬜ coherence check (sheet ready) |
| Theme names | The name says more or less than the problems inside | Read the name against its member phrases. One case found: "US and international trading options" also holds fixed deposits and an education section | 🟡 read by me, formal check pending |
| Live "try it on a review" | Same as the first five rows | The same validation runs before anything is shown, and a failure shows a message instead | ✅ |
| Weekly brief | No model writes its sentences, so nothing to invent there | Numbers and quotes are checked on every brief. It still inherits mistakes in labels and theme names from above | ✅ |
| Chat agent (planned) | Invents a number or quote, answers without evidence | Every number traced to a tool result, "no evidence" test questions | 🔒 |
| Labelers used as references | Their own mistakes become "the truth" | The same validator is applied to their labels, two independent labelers are compared, severity is checked against my own ratings | 🟡 |

Signals to watch over time (rejection reasons are now logged on every run): how often answers are rejected and why, how many quotes are altered versus invented, how often the one-at-a-time fallback is needed (21 of 99 in the last run), how often two labelers disagree on a flag, and whether the same review gets the same labels when run twice (⬜).

### 10.4 Go / no-go before the portfolio goes public
Must have:
1. Human check of categories on at least 60 reviews. ⬜
2. Test split scored once. ⬜
3. Formal theme coherence check. ⬜
4. Gate missed-signal sample of at least 150 skipped reviews. ⬜
5. Severity validated on at least 15 human-rated critical cases. 🟡
6. Release comparison tested with no-change and injected-spike cases. ✅ (low false alarms, modest sensitivity)
7. Sessions with 3 PMs (time to a fix list, understanding). ⬜
8. Instruction-injection test on the reader. ⬜
9. Cost and latency table published. 🟡 cost done, latency numbers come with the next model run
10. Final scan: no secrets, no personal data, in the repository and the app. 🟡 scan built and passing, rerun right before publishing

Nice to have: a paid-model benchmark, a stability rerun, and the checks for the brief and the chat agent once they exist.

### 10.5 Order of work (cheapest first)
1. No tokens, no cost: theme coherence check (2 minutes, sheet ready), release no-change and injected-spike tests (done), save per-call latency (done), cost table (done), privacy and secrets scan (done).
2. Free labels: gate missed-signal sample, instruction-injection test.
3. My time: blind human check of 60 category labels, 3 PM sessions.
4. Free-tier tokens, one day each: test split once, stability rerun.
5. When spending is fine: paid-model benchmark.

### 10.6 Evaluation data we have
- Golden set: 400 reviews (200 dev, 200 test), stratified, labeled by a second AI labeler. Not human-verified.
- My ratings: 40 aspects (dev) and 30 fresh reviews, severity only.
- Second-labeler comparison: 99 reviews labeled independently by two labelers.
- Baselines: stars only and keyword rules.

### 10.7 Reporting rules
Every number appears with its count, its baseline, who labeled it, and its limits on the same page. Failures are included, and any change made after seeing results is logged with the reason.

## 11. Success metrics

| Layer | Metric | Target |
|---|---|---|
| Product | Time to a prioritized fix list | < 15 min (baseline measured) |
| Product | Share of brief claims with valid citations | ≥ 95% |
| AI quality | Bars in section 10 | Met, or honestly reported as missed |
| Efficiency | Share of reviews skipped by the gate with no accuracy loss | Report measured value |
| Cost | Dollars per 1,000 reviews | Report, plus the projected monthly cost for 130 reviews a day |
| Portfolio | Number of external PMs who rate the brief usefulness | 3 to 5 |

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Very few substantive reviews (about 9 a day) make rare classes statistically thin | Confidence intervals, minimum-n rules, weekly forward collection |
| Golden set uses much of the rare data | Keep fresh weekly data as an unseen check set |
| AI labels are not independently verified | Different model family for labeling, postponed human subset, wording discipline in the case study |
| Missing-version reviews are biased negative | Show as an explicit bucket, never drop |
| Hinglish and mixed-script text | Slice reporting, multilingual embeddings, include in golden set |
| LLM fabricates numbers or quotes | Code computes numbers, quotes verified as substrings, claim-citation post-check |
| Defamation risk from restating fraud claims | Attribution rule, separate trust-and-risk view |
| Play Store scraping limits and terms | Use only public data, light request rate, no personal data stored, check terms before any public demo |
| Review bias (vocal minority) | Visible caveat and sample size on every insight |
| Scope creep into chat and extra sources | D1 and D2 first, chat last, non-goals enforced |

## 13. Milestones

1. **M0 (done):** problem framing, data pull and profile, golden-set sample, labeling guide v1.0, validator.
2. **M1:** AI labels for dev and test sets validated. PRD v1.0 signed off.
3. **M2:** System and prompt spec (schemas, prompts, tool definitions, clustering approach).
4. **M3:** Extraction plus gate plus aggregation working on dev set. First eval run against baselines.
5. **M4:** Themes, ranking and regression detection (D1, D2). Brief generator with citation checks.
6. **M5:** Model benchmark, test-set evaluation, human-labeled subset added.
7. **M6:** Chat agent, UI polish, case study, demo video.

## 14. Decisions and open questions

### Decided
1. UI: Streamlit.
2. Minimum theme size 5 reviews. Minimum version or window sample 30 reviews.
3. Severity weights 8 / 4 / 2 / 1 (critical / high / medium / low), adjustable in the UI. Revisit after the first evaluation.
4. Public demo: frozen snapshot.
5. Labeling: AI labels guided by labeling guide v1.0. Human blind subset postponed.
6. Taxonomy: 12 categories, with fraud and money-loss claims separate and customer support kept but non-product.

### Open
1. Which embedding model handles Hinglish well. Needs a small test on the dev set.
2. When to add the human-labeled subset: before M5 at the latest, and before any "human-verified" claim.
3. Which model families to benchmark, and which family does the labeling.

### 8.2 Interface decision (2026-10-31)
Streamlit confirmed (product owner's choice, for a portfolio piece that a PM can also use). The app (`app/streamlit_app.py`) reads a frozen snapshot (`app/snapshot.json`), so all pages except the live "Try it on a review" load instantly. Pages: What to fix, Theme detail, Releases, How reliable is this?, Try it on a review. PM controls: date range, severity weights, minimum theme size, categories.

### 8.3 Weekly brief (built 2026-11-01)
First tab of the app. A PM picks the last 7 days, last 14 days or the whole sample and gets a one-page brief in my voice: headline numbers against the previous period, what to fix first (product problems), what people are asking for (feature requests), what is rising, trust and risk (fraud claims, labeled as claims), support, and release health, each with real quotes and the review they came from. It can be downloaded as text. It is written by code from templates, so no model touches a sentence, and every brief runs automatic checks before it is shown.

### 8.4 Public demo (decided 2026-11-01)
Streamlit Community Cloud, public repository with safe files only, live "Try it on a review" enabled with limits (5 per visitor, 40 per day across visitors, key stored as a host secret). The public app shows invented reviews for a fictional app, because reviews belong to their authors and the way the real ones were collected conflicts with Google's robots.txt (`docs/data_terms_note.md`). A check that compares every public file against the real reviews must pass before publishing (`scripts/public_check.py`).
