# PRD: Voice of Customer Copilot

## Overview

Voice of Customer Copilot reads app-store reviews and tells a product manager what to fix first. It ranks problems by how serious and how widespread they are, flags releases that made things worse, and writes a weekly brief where every claim comes with real quotes.

The value is trust, not summarizing. Every insight shows its evidence, every number comes from code, and when the data is thin the product says "not enough evidence" instead of guessing.

## Problem

A PM on a consumer finance app gets around 130 reviews a day and can't read them all. The usual process is skimming recent 1-star reviews on a Monday. That leaves three questions open: which complaints are real, which are growing, and how to defend the choice to engineering or leadership.

I looked at 36 days of public reviews for one investing app (4,600 reviews) to see how much signal there actually is:

- 78% are 5 stars, and 71% are three words or fewer.
- Only about 336 reviews are real complaints (1 to 2 stars, 8 or more words). That is roughly 9 a day.
- The real work is finding those 9 a day and showing whether they are growing.

## Users

| | |
|---|---|
| Primary | Maya, a product manager who owns a squad (trading, payments or onboarding). She ships every one to two weeks, has little time, doesn't trust AI summaries, and needs evidence she can forward. |
| Later | Engineering leads (bug triage), support operations, leadership |

Maya has five decisions to make, and the product is built around them:

- What should we fix this sprint?
- Did the last release break something?
- Is this a bug, a design problem or a feature request?
- What are users asking for that we don't have?
- What do I tell leadership?

The first two carry most of the value, so I built them first.

## Goals and success metrics

| Goal | Target |
|---|---|
| Speed | A fix list in under 15 minutes. Today it takes roughly two hours of manual reading. |
| Evidence | Every claim traces back to a verbatim review quote. |
| Reliability | Critical issues caught: at least 90%. Problem-finding score (F1): at least 0.75. Sentiment agreement (kappa): at least 0.70. I wrote these bars down before seeing any results. |
| Releases | Spot a release that made things worse within days. The alarm should stay quiet when nothing changed. |
| Discipline | Use AI only where it beats a simple non-AI baseline, and prove it with numbers. |

## Scope

**In scope for v1:** one app, one review source (Google Play), English and Hinglish, one persona, a weekly or on-demand batch.

**Out of scope:** competitor tracking, churn prediction, replying to reviews, other review sources, private analytics such as funnels and crash logs, real-time alerts.

## How it works

Reviews → clean → filter → AI reads each review → code decides severity → group into themes → code ranks and checks releases → weekly brief.

| | |
|---|---|
| Code | Removing personal data, the filter, checking every AI answer, severity, all counts and rankings, the release statistics, the brief |
| AI | Reading each review (category, sentiment, problems, quotes, true/false facts) and deciding which small groups of problems mean the same thing |
| Why this split | Reviews are free text with mixed Hindi and English, sarcasm and half sentences, which suits AI. Counting, ranking and statistics must be exact and repeatable, which suits code. |

Each review gets one of 12 categories: order execution, payments and funds, login and account, crash or bug, performance, UX friction, feature request, charges and pricing, customer support, fraud or money-loss claim, praise, other. The last four never enter the fix list. Fraud and money-loss claims get their own section, labeled as claims.

## Requirements

**The rule behind every requirement: AI reads, code decides and counts.** A model never produces a number you see.

| Requirement | What it means |
|---|---|
| Clean and filter | Remove names, photos and developer replies at the first step. A rule-based filter drops reviews with no signal (about 77% of them). It must miss at most 2% of real complaints. |
| Read each review | The AI picks a category, sentiment, the specific problems, a word-for-word quote for each, and answers eight true/false questions (money lost, money stuck, order went wrong, a main action blocked, and so on). Code checks the answer. A quote that isn't really in the review is rejected and redone. |
| Severity | Code decides, using rules I wrote. The AI only supplies the true/false facts. Money lost, an order that went wrong or a security issue means critical. |
| Themes | Similar problems are grouped. A theme needs at least 5 reviews to be ranked. Smaller groups show as "emerging, low evidence". |
| Ranking | Priority = severity points × trend. The formula and weights are visible, and the PM can change them. |
| Release check | Flag a version only with at least 30 reviews on each side, a statistical test, and a rise of at least 1.5×. Otherwise say "not enough evidence". |
| Weekly brief | Written by a template from code-computed numbers. A self-check confirms every number matches and every claim has a quote. |
| Fintech safety | Money-loss and fraud claims are always attributed ("a reviewer says…"), never stated as fact. No personal identifiers anywhere. |

## How I decide it works

I wrote a checklist of 94 checks, one stage at a time, because a single overall accuracy number hides where a bad insight came from. Each check says how it's measured, what the bar is, and where it stands today: 48 measured, 25 partly measured, 21 not done yet. I wrote the bars down before I saw any results. These are the ones that matter most:

| Stage | What I check | Bar |
|---|---|---|
| Cleaning | No names, photos, developer replies or personal details left in the stored data or the app | None found |
| Filter | Real complaints it wrongly skips (I label a random sample of the skipped reviews) | At most 2% |
| Reading | Problem finding (F1), categories (macro F1), sentiment (kappa), and whether it beats a keyword baseline | 0.75, 0.80, 0.70, clear lift |
| Quotes | Every quote appears word for word in the review. Rejected answers are logged and sorted as altered, reworded or invented | 100% |
| Severity | Critical issues caught, and critical calls that were right, against my own ratings. Never two or more levels off in the dangerous direction | 90% and 70% |
| Themes | Is each ranked theme one problem with one owner? I read them myself. Also how many problem reviews land in a ranked theme | 85% coherent, 60% coverage |
| Ranking | Formulas tested, I agree with the top 5, and a PM can explain the priority score | 4 of 5 overlap, 2 of 3 PMs |
| Release check | Stays quiet when I shuffle versions so any difference is chance, and catches an injected jump. I report how big a change it needs | Near-zero false alarms |
| Weekly brief | Every number matches the code, and every claim has a real quote from the review it cites | 100% |
| Made-up content | Instructions hidden inside a review, and gibberish or emoji-only reviews, must not change the output | No change |
| Cost and speed | Tokens per review, cost per 1,000 reviews by model, time per page and per live review | Reported |

A few rules I kept: tune on practice data and score the held-out set once, always show how many cases a number rests on, compare against a simple baseline, and write down every change I made after seeing results. The references are kept separate: my own severity ratings, a second labeler on 200 reviews, and two independent labelers on 99 reviews. Results are in the [case study](case_study.md). The full row-by-row checklist is in [evaluation_checklist.md](evaluation_checklist.md).

## Risks and open questions

- **A real quote with the wrong label.** Code can catch made-up text but not a wrong category. Only people and cross-checks catch that, so a human check of about 60 category labels is still open.
- **Reviews are a vocal minority.** Every theme shows its sample size and a "directional only" note.
- **Few serious cases to test on.** Only 7 of my 30 test reviews were critical, so the severity result is encouraging, not proven.
- **Free tools cap the volume.** I built it on free model limits, so the larger test runs were slow and rationed.
- **Still to do:** score the held-out test set once, and watch PMs use it.
