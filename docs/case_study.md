# Voice of Customer Copilot: case study

## The short version

A PM at a consumer finance app gets about 130 app-store reviews a day and has no good way to tell which complaints are real, which are growing, and which are worth fixing. I built a copilot that reads the reviews, ranks the problems, flags releases that made things worse, and writes a weekly brief with real quotes as proof.

The AI was the easy part. The harder part was deciding where AI should not be used, and finding out where it was wrong.

## The problem

I worked with 4,600 public Play Store reviews of an investing app, collected over 36 days. I wanted to know how much of it is useful. 78% are 5 stars and 71% are three words or fewer. Only about 336 are real complaints, which is around 9 a day.

So the PM isn't short of reviews. They're short of a way to find those few and see which ones are growing. Skimming recent 1-star reviews on a Monday can't tell you that, and it can't help you defend a choice to engineering.

## How it works

One rule shaped everything: **the AI reads, and code decides and counts.** No number on the screen comes from a model.

| Step | Who does it |
|---|---|
| Clean | Code removes names, photos and developer replies |
| Filter | Code rules drop reviews with nothing to learn from (77% of them) |
| Read | AI labels each review: category, sentiment, the problems, a word-for-word quote, and eight true/false facts |
| Check | Code rejects any label whose quote isn't actually in the review |
| Severity | Code, using rules I wrote |
| Themes | Word matching first, then an AI step that merges groups that mean the same thing |
| Rank and brief | Code ranks themes, checks releases and fills a brief template |

## Four decisions that shaped it

**1. I took severity away from the AI.**
My first version asked the model how serious each problem was. I rated 70 cases myself and compared. The model caught only 11 of the 27 issues I had rated critical (41%), and rewriting the instructions didn't help (37%).

So I changed the job. The model now answers eight yes/no questions: was money lost, is money stuck, did an order go wrong, is a main action blocked, and so on. Then code applies rules I can read and change. On 30 new reviews I rated myself, it caught 7 of 7 critical issues, and 7 of its 9 critical calls were right (78%). It landed within one level of my rating 97% of the time. Only 7 of those reviews were critical, so I call this encouraging, not proven.

**2. My own scoring rule was wrong, and I found out.**
My first rule counted a problem as "found" only if the two quotes overlapped heavily. It gave a score of 0.38, which looked terrible. The real cause was that one labeler quotes whole reviews and the other quotes short phrases. 101 of 185 correct matches were being counted as misses. I changed the rule to compare the shorter quote against the longer one, wrote down why, and the score became 0.85. I made that change on practice data only. The held-out test set stays untouched.

**3. Word matching alone didn't group problems well enough.**
It turned 252 problems into 147 themes, and only 6 had five or more reviews. That's too scattered to rank. I added a step where a model decides which small groups mean the same thing. It can only merge groups that already exist, and never across categories. The result was 95 themes, 10 of them ranked, and the share of problem reviews inside a ranked theme went from 27% to 56%. When I read the ten ranked themes myself, seven were clearly coherent and three were a bit broad.

**4. The release alarm is cautious on purpose.**
It flags a version only with 30 or more reviews on each side, a proper statistical test, and a rise of at least 1.5 times. To test it, I shuffled which version each review belonged to, so any difference was pure chance. It raised a false alarm 0.9% of the time (18 of 2,000). I also injected real increases. With 80 reviews per version, a doubling of complaints was caught 74% of the time. A 1.6× rise was caught only 23% of the time. So "no flag" doesn't mean "no problem", and the app tells you that.

## How I checked it

I used three kinds of reference and kept them separate, because they are not equally trustworthy: my own ratings (the strongest), a second labeler on 200 reviews, and two labelers working independently on the same 99 reviews.

| What | Result |
|---|---|
| Problem finding on 200 reviews (precision / recall / F1) | 0.83 / 0.86 / **0.85**. A keyword-rules baseline scored 0.55, and ranking by star rating alone scored 0.04. |
| Category score (macro F1) | 0.83 |
| Sentiment agreement (Cohen's kappa) | 0.97 |
| Two independent labelers on 99 reviews | Sentiment kappa 0.96, severity weighted kappa 0.81, problem finding F1 0.75 |
| Quotes the model made up | 1 in 67 (1.5%) in a first look, caught by code. Another 3 were lightly altered and also caught. |

Every number can be recomputed with one command. I wrote the pass/fail bars down before I saw any result.

## What went wrong, and what I'd do differently

- **Free tools set my schedule.** The free model plan allows 8,000 tokens a minute and 200,000 a day. A 200-review run took about 20 minutes, and I hit the daily limit several times. I added automatic waiting, clean stops and a cache so reruns cost nothing. Next time I'd measure tokens per review before writing the prompt, because my long rulebook was most of the cost.
- **I can't yet prove the filter is safe.** It missed none of 129 real complaints in my sample, but only about 25 reviews in that sample were skipped. That's too few to prove my bar of at most 2% missed.
- **The model seems to over-use "order went wrong".** Of 11 reviews where two labelers disagreed on a fact, the pipeline said this three times for things that look like a display glitch or a lottery, not a wrongly placed order. That's my reading, not a formal check, so I left the wording unchanged.
- **Short praise splits the labelers.** "Easy to use" is useful praise to one and nothing to analyse to the other, so they agree on only 75% of "usable" calls. It doesn't change the fix list.

## What the results are based on

- The results come from public reviews I can't republish, so the live demo uses invented ones.
- Names, photos and developer replies were removed first.
- The 200-review comparison is against a second AI labeler following my labeling guide. It is not human-verified.
- The severity ratings (70 cases) are mine.
- The pipeline ran on free-tier models. I didn't test a paid one.

## What it costs

About 1,090 tokens per review. On a free tier that's $0. On a paid tier it ranges from about $0.22 per 1,000 reviews (cheapest) to about $8.60 (top tier). At this volume, cost isn't what decides the model. Quality on mixed Hindi-English text and on severity is.

## What I'd do next

- Check about 60 category labels myself.
- Score the held-out test set, once.
- Watch two or three PMs use it: how long to a fix list, and whether they understand the priority score.

[Try the live app](https://voice-of-customer-copilot-f6achlhlvutr6xyye3sdms.streamlit.app/) · [Code on GitHub](https://github.com/namratas798/voice-of-customer-copilot)
