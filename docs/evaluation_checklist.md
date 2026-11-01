# Evaluation checklist (detail behind the PRD)

The full stage-by-stage checklist behind the PRD's evaluation section. Covers only what is built.

This is what I check, in order, before I trust the flow or show it to anyone. Each row says what to check, how, the bar, and where we are. The bars were set before the results were seen and stay provisional until the first test-set run.

Status key: ✅ measured | 🟡 partly measured or weak evidence | ⬜ not done yet

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
| 9 | App | code | PM task test |
| 10 | Live "try a review" | the same reader | latency and failure tests |

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

Nice to have: a paid-model benchmark, a stability rerun.

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

