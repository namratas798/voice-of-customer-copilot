# Voice of Customer Copilot: case study (draft)

*Draft written from the project's real numbers. Rewrite it in your own words. Lines marked [YOUR WORDS] are for your story, which only you can tell. Keep the "Data and labels" section honest when you edit.*

---

## In one paragraph
A PM at a consumer finance app gets about 130 app-store reviews a day and has no way to tell which complaints are real, growing and worth fixing. I built a copilot that reads the reviews, ranks problems by how serious and widespread they are, flags releases that made things worse, and writes a weekly brief with real quotes as evidence. The interesting part was not the AI. It was deciding **where AI should and should not be used**, and **proving where it was wrong**.

## The problem
- I worked with public Google Play reviews of Groww, an investing app. [YOUR WORDS: why this app, why this problem]
- 4,600 reviews over 36 days, about 128 a day.
- 78% are 5 stars and 71% are three words or fewer ("good app"). Only about 336 are real complaints (1 to 2 stars, 8 or more words), around 9 a day.
- The assumed process is skimming recent 1-star reviews on Monday, without being able to tell which complaints are growing, which are serious, or to defend a choice to engineering. [YOUR WORDS: confirm this matches the PMs you know]

## Who it's for and what it decides
Maya, a PM who ships every one to two weeks. Six decisions: what to fix this sprint, did the last release break something, bug versus design problem versus feature request, what users ask for that we don't have, what to tell leadership, and an ad-hoc "why is X happening?".

## How it works
```
reviews -> clean -> gate (rules) -> AI reads each review -> code decides severity
        -> group into themes (word matching + AI merge) -> code ranks and checks releases -> weekly brief
```
**The rule I held to: the AI reads, code decides and counts.** No number you see ever comes from a model.

| Step | Done by |
|---|---|
| Remove names and photos, drop duplicates | code |
| Drop reviews with no signal (23% pass) | code rules |
| Label each review: category, sentiment, problems, quotes, true/false facts | AI model |
| Check the label (valid values, quote really in the review) | code |
| Turn the facts into a severity | code, rules I wrote |
| Group similar problems | word matching, then an AI merge step |
| Rank themes, compare releases, write the brief | code |

## Four decisions that shaped it

**1. Severity: why I took it away from the AI.**
The first version asked the model how serious each problem was. I rated 70 cases myself and compared. The model caught only **41% (11 of 27)** of the issues I rated critical. A rewrite of the instructions made no difference (37%).
The fix was to change the job. The model now answers eight true/false questions (money lost? money stuck? order went wrong? a main action blocked?) and code applies rules I wrote and can read. On 30 fresh reviews I rated and the rules were not built on: **7 of 7 critical issues caught, 7 of 9 critical calls right (78%), 97% within one level of my rating.** Only 7 cases were critical, so I treat this as encouraging, not proven.

**2. My own metric was wrong, and I found it.**
My first scoring rule counted a problem as "found" only if the quotes overlapped heavily. It gave a problem-finding score of 0.38, which looked terrible. The real cause: one labeler quotes whole reviews and the other short phrases, so 101 of 185 correct matches were scored as misses. I changed the rule to compare the shorter quote against the longer one, logged why in a changelog, and the score became **0.85**. I did this on the practice data only, and the held-out test set stays untouched.

**3. Themes: word matching alone wasn't enough.**
Grouping by matching words produced 147 themes from 252 problems, and only 6 had five or more reviews. I added a step where a model decides which small groups mean the same thing. It can only merge groups that already exist and never across categories. Result: **95 themes, 10 ranked, and the share of problem reviews inside a ranked theme went from 27% to 56%.** My own read of the ten ranked themes: seven clearly coherent, three slightly broad.

**4. The release alarm is deliberately cautious.**
It flags a version only with 30 or more reviews on each side, a solid statistical test, and a rise of at least 1.5 times. I tested it with simulations. Shuffling which version each real review belonged to (so any difference is pure chance) raised a false alarm **0.9% of the time (18 of 2,000)**. Injected real changes: with 80 reviews per version, a doubling of the complaint share was caught 74% of the time (96% with 150 reviews), and a 1.6x rise only 23%. So "no flag" does not mean "no problem", and the app says what it can and can't see.

## How I checked it
Three kinds of truth, kept separate:
1. **My own ratings** (the strongest): 70 cases of severity.
2. **A second labeler** for categories and problems on 200 reviews.
3. **Two labelers working independently** on the same 99 reviews, to see how consistent the task is.

| What | Result |
|---|---|
| Problem finding on 200 reviews: precision / recall / F1 | 0.83 / 0.86 / **0.85** (keyword-rules baseline **0.55**, stars-only **0.04**) |
| Category score (macro F1) | 0.83 |
| Sentiment agreement (Cohen's kappa) | 0.97 |
| Two labelers on 99 reviews: sentiment / severity (weighted kappa) | 0.96 / 0.81 |
| Two labelers: problem finding, precision / recall / F1 (praise excluded) | 0.83 / 0.68 / 0.75 |
| Quotes the model invented (partial check on 84 saved answers) | 1 in 67 (1.5%), all caught by code |
| Quotes lightly altered (same check) | 3 in 67, all caught |

Every number is reproducible with one command, and the bars were written down before I saw results.

## What went wrong, and what I'd do differently
- **Free tools set the schedule.** The free model plan allowed 8,000 tokens a minute and 200,000 a day. A 200-review run took about 20 minutes and I ran out of daily allowance several times. I added automatic waiting, clean stops, and a cache so reruns cost nothing. In hindsight I'd measure token use per review before designing the prompt, because the long rulebook was most of the cost.
- **The gate's safety isn't proven.** It missed none of 129 actionable reviews in my sample, but only about 25 reviews in that sample were skipped, so it can't prove the bar I set (at most 2%).
- **The model seems to over-trigger "order went wrong".** In the 11 reviews where the two labelers disagreed on a fact, the pipeline claimed it three times for what look like a display glitch, trading errors and an IPO lottery, not wrongly executed orders. That is a read, not a formal check, and I left the wording unchanged.
- **Short praise splits the labelers.** "Easy to use" is usable praise to one and nothing to analyse to the other, so they agree on only 75% of "usable" calls. It doesn't affect the fix list.
- **I haven't run the held-out test set**, had no PM try it, or done a human check of categories. I list these as open.

## What it costs
About 1,090 tokens per review (820 in, 270 out).

| Model tier | Per 1,000 reviews | Per month at today's volume (about 30 reviews a day through the gate) |
|---|---|---|
| Free tier | $0 | $0 |
| Cheapest paid | about $0.22 | about $0.19 |
| Mid tier | about $2.2 | about $1.9 |
| Sonnet-class | about $4.3 | about $3.9 |
| Opus-class | about $8.6 | about $7.8 |

At this volume cost isn't the deciding factor. Quality on Hinglish and severity is. The gate skips 77% of reviews, but its real value is less noise, not money.

## What I'd do next
A human check of category labels on about 60 reviews, score the held-out test set once, sessions with PMs (time to a fix list, whether they understand the priority score), and the chat agent with read-only tools.

## Artifacts
- A product spec with a full evaluation checklist (106 checks, each with how, bar and honest status: 48 measured, 25 partly measured, 21 not done, 12 for features not built yet).
- A labeling guide, a severity rulebook, and changelogs for every prompt, rule and scoring change.
- 68 automated tests.
- The app: Weekly brief, What to fix, Theme detail, Releases, How reliable is this?, Try it on a review. [SCREENSHOTS HERE]

---

## Data and labels (keep this honest when you rewrite)
- **The public app uses invented reviews for a fictional app.** The results in this case study were measured on real reviews that I can't publish (`docs/data_terms_note.md`).
- **Before publishing anything with review text, read `docs/data_terms_note.md`.** Google's robots.txt disallows the path the collection tool used, and reviews belong to their authors.
- Reviews: 4,600 public Google Play reviews of one app over 36 days. Names, photos and developer replies were removed at the first step.
- Golden set: 400 reviews (200 for tuning, 200 held out), labeled by a second AI labeler (Cursor) following my labeling guide. It is not human-verified.
- Severity ratings: 40 aspects and 30 fresh reviews, rated by me.
- A random sample of 504 reviews was labeled by ChatGPT, run by me, using the same guide and the same true/false questions. The app's snapshot is built from that sample.
- The pipeline's own run on 99 of those reviews was compared with ChatGPT's labels. Neither is treated as truth, and the two may agree more than unrelated models would.
- Models used in the pipeline: gpt-oss-120b and gpt-oss-20b on Groq's free tier. No paid model was tested.
