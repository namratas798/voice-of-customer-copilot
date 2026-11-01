# How every number on "How reliable is this?" is measured

For explaining the page to someone. Plain words first, formulas second, then the honest limits.

## 1. The one-minute version

The tool reads reviews and produces labels: what the problem is, how the person feels, how serious it is. The page answers one question: **how often do those labels match a trusted reference?**

There are three kinds of reference, because "trusted" comes in degrees:
1. **My own ratings.** The strongest reference. I rated severity myself and compared the tool with me.
2. **Another AI's labels.** A reference to compare against, but only a second opinion, not the truth.
3. **A second labeler working independently.** Two labelers, same reviews, neither assumed right. It shows how consistent the task is.

Nothing on the page is calculated when someone opens the app. These are **saved results from test runs**, computed offline by scripts and stored in the app's data file.

## 2. Who does what

| Job | Done by |
|---|---|
| Read each review and label it (category, sentiment, problems, quotes, true/false facts) | **AI model** |
| Check the label is well formed (valid category, quote really appears in the review) | **Code** |
| Turn the AI's facts into a severity level (critical, high, medium, low) | **Code**, using rules I wrote and approved |
| Decide what counts as a match, and calculate every score on the page | **Code** |
| The reference for severity (70 ratings in total) | **Me, a human** |
| The reference for categories and problems on 200 reviews | **A second AI labeler** (not human-checked) |
| The second independent labeler on 99 reviews | **ChatGPT**, run by me |
| The simple comparison ("baseline") | **Code**: keyword rules, no AI |

The principle behind it: **the AI reads, code decides and counts.** An AI never produces a number you see.

## 3. Block 1: Severity ("Checked on 30 reviews I rated myself")

**How the test was set up**
- 30 reviews the rules were not built on: 20 picked because they look serious (words like money, stuck, withdraw, order), 10 random negatives. None were in the golden set.
- I rated each one for **the most serious problem in the review**, on five levels: none, low, medium, high, critical, without seeing what the model said.
- The AI labeled the same reviews. For each problem it answered true/false questions (did money get lost? is money stuck? did an order go wrong? ...). Code turned those answers into a severity. A review's severity is the **highest** among its problems.
- A script then compared the model with my ratings.

**The four numbers**
| On the page | What it means | Formula | Result |
|---|---|---|---|
| Critical issues caught (recall) | Of the reviews I rated critical, how many did the model also call critical? | both critical ÷ I said critical | 7 of 7 |
| Critical calls that were right (precision) | Of the reviews the model called critical, how many did I also rate critical? | both critical ÷ model said critical | 7 of 9 (78%) |
| Exact severity match (accuracy) | Same level | same level ÷ all reviews | 21 of 30 (70%) |
| Off by at most one level (±1 accuracy) | Same level or next to it on the five-step scale | (difference ≤ 1) ÷ all reviews | 29 of 30 (97%) |

**Why both recall and precision:** recall alone can be gamed by calling everything critical. Precision alone can be gamed by almost never calling anything critical.

**Why severity works this way at all:** the first version asked the AI for the severity directly. It caught only 41% of the critical cases I had rated. So I split the job: the AI reports facts, code applies rules. That redesign is why this block exists.

## 4. Block 2: Reading the reviews ("Checked on 200 reviews against reference labels")

**Setup:** 200 reviews from the golden set, labeled by a second AI following the same written labeling guide (the reference). The pipeline labeled them too (first version of the prompt, before the severity redesign).

**The matching rule (the heart of the scoring).** A model's problem counts as the same as a reference problem if:
1. they have the **same category**, and
2. their quotes **overlap by at least half**: shared words ÷ words in the shorter quote ≥ 0.5.
   Example: reference quote "refund delayed, my money is stuck, support unreachable" and model quote "my money is stuck" share 4 words, and the shorter quote has 4 words. 4 ÷ 4 = 1.0, so it is a match.
Each reference problem can be matched once. Unmatched ones are misses, unmatched model problems are inventions.

| On the page | What it means | Formula | Result |
|---|---|---|---|
| Problem-finding (precision) | Of the problems the model found, how many are in the reference. Low means it invents problems | matched ÷ problems the model found | 0.83 |
| Problem-finding (recall) | Of the reference problems, how many the model found. Low means it misses problems | matched ÷ reference problems | 0.86 |
| Problem-finding score (F1) | One number balancing the two | F1 = 2 × precision × recall ÷ (precision + recall) | 0.85 |
| Category score (macro F1) | The same, worked out per category, then averaged equally (**macro F1**) so small categories count as much as big ones | average of the per-category F1 | 0.83 |
| Sentiment agreement (Cohen's kappa) | Do they agree on positive versus negative beyond chance? | (agreement − chance agreement) ÷ (1 − chance agreement) | 0.97 |
| Keyword-rules baseline (F1) | The problem-finding score for a no-AI keyword approach | same F1 | 0.55 |

**A real worked example of F1** (from the two-labelers block, problems only): one labeler found 50 problems, the other 41, and 34 matched. Precision = 34 ÷ 41 = 0.83. Recall = 34 ÷ 50 = 0.68. F1 = 2 × 0.83 × 0.68 ÷ (0.83 + 0.68) = **0.75**.

**Why kappa and not "% agreement":** if 85% of reviews are negative, two labelers who just always say "negative" already agree 85% of the time. Kappa subtracts that luck. Illustration (not our data): 90% raw agreement with 85% negative on both sides gives chance agreement 0.85² + 0.15² = 0.745, so kappa = (0.90 − 0.745) ÷ (1 − 0.745) = 0.61. 1.0 is perfect, 0 is no better than chance.

**Why the keyword baseline is there:** a score only means something next to an alternative. 0.85 against 0.55 says the AI adds a lot over simple rules.

## 5. Block 3: Two labelers, same reviews ("99 reviews labeled twice, independently")

**Setup:** 99 reviews labeled by ChatGPT (run by me, following the same guide) and, separately, by the pipeline. Neither is treated as the truth. This measures **consistency**, not accuracy.

| On the page | What it means | Formula | Result |
|---|---|---|---|
| Sentiment agreement (Cohen's kappa) | Same positive/negative call beyond chance | kappa, as above | 0.96 |
| Severity agreement (weighted kappa) | Same severity, where a near miss is penalised less than a far miss: each step apart on the five levels counts as one quarter of a full disagreement | weighted kappa | 0.81 |
| Problem-finding (precision) | Taking one labeler as the reference: of the problems the other found, how many match. Praise and "other" removed, because praise does not affect the fix list | matched ÷ problems the other found | 0.83 (34 ÷ 41) |
| Problem-finding (recall) | Of the reference labeler's problems, how many the other also found | matched ÷ reference problems | 0.68 (34 ÷ 50) |
| Problem-finding agreement (F1) | One number balancing the two | F1 | 0.75 |
| Agreement on usable reviews (% agreement) | Both say the review has something worth analysing, or both say it does not | agree ÷ all | 74 of 99 (75%) |

**Why "usable" is only 75%:** most disagreements are short praise such as "Easy to use". One labeler treats it as a usable praise, the other as nothing to analyse. The guide's wording does not settle it. Praise does not change the fix list.

## 6. Bars set in advance
The targets were written down before the results were seen (`docs/evaluation_checklist.md`): for example critical issues caught at least 90%, problem-finding score at least 0.75, sentiment kappa at least 0.70, theme coherence at least 85%. A result that misses its bar is reported as missed.

## 7. How to recompute any number
| Number | Command (from the project folder) |
|---|---|
| Severity block | `.venv/bin/python -I scripts/score_validation.py data/golden/human/severity_ratings_val30.csv data/golden/validation/validation_key.csv runs/v4flags_20b_val30/labels.jsonl` |
| Reading block | `.venv/bin/python -I scripts/voc.py eval --split dev --pred runs/dev_gptoss120b_v1/labels.jsonl` (baseline: `--pred runs/baseline_kw_dev/labels.jsonl`) |
| Two-labelers block | `.venv/bin/python -I scripts/compare_labelers.py runs/agreement108_inputs.jsonl data/external_labeling/chatgpt_labels.jsonl runs/pipeline_20b_agreement108/labels.jsonl GPT pipeline` |

## 8. Honest limits (say these before someone asks)
- **Only 7 of the 30 reviews were critical.** "7 of 7" is encouraging, but with so few cases the true catch rate could be much lower.
- **The 200-review block compares against another AI, not a person.** It shows consistency with a second reader, not proven accuracy. A human check of categories is still to do.
- **The first test run was before the severity redesign.** In that run the model caught only 39% of the critical cases, which is why severity was redesigned. The page shows the redesigned severity result in the severity block.
- **Two labelers from related model families may agree more than two unrelated ones would.**
- **Some choices were made after seeing results**, such as the overlap matching rule and the problems-only view. Each is logged with its reason in `docs/eval_changelog.md` and `docs/prompt_changelog.md`.
- **The numbers come from samples** (a random sample of reviews that pass a filter), not every review.

## 9. Questions you might get
**"Why should I trust AI to grade AI?"** You shouldn't, on its own. That is why severity, the part that matters most, is checked against my own ratings, and why the other blocks are labeled as agreement, not accuracy.

**"Is 7 out of 7 good?"** It is a good sign on a small number. I would want at least 15 critical cases before relying on it.

**"What does 0.85 mean in practice?"** Across the problems either of them found, they agree on most but not all. It is much better than a keyword approach (0.55). It is not perfection, and it's not human-checked.

**"Why is severity done by rules?"** When the AI judged severity directly it missed more than half of the serious cases. Having it report facts and letting rules decide is more accurate, and I can read and change the rules.

**"What would make you more confident?"** A human check of categories on about 60 reviews, a clean score on the held-out test set, and a larger set of critical cases rated by me.

## 10. How we know whether the model made something up
Two kinds of mistake, and they are caught differently.

**Made-up text (caught by code, measured).** Every quote the model gives must appear word for word in the review. If it doesn't, the answer is rejected, redone, and if it still fails it is marked failed, never kept. Every run saves a rejection log (`rejections.jsonl`, summary in `run.json`) with the reason for each rejection. Quotes that fail are split into three kinds by comparing them with the closest text in the review: **altered** (a dropped word or punctuation), **paraphrased** (reworded) and **invented** (not in the review). First look at 67 quotes: 3 altered, 0 paraphrased, 1 invented (1.5%), all caught.

**A real quote with the wrong label (not caught by code).** The model picks a category or a fact such as "money lost" that the text doesn't support. The only ways to find these are people and comparison: my own severity ratings, a second labeler (a fact only one of them sets is a suspect), and a human check of categories. This is the larger risk, and the PRD lists it as still open.
