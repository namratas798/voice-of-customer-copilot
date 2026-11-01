# Eval changelog

Every change to how we score, with the reason. Bars and rules are meant to be fixed in advance, so each entry says what was seen and which data was used.

## 2026-10-31: aspect matching rule v1 to v2
- **v1:** two aspects match if the category is equal and the quote word sets have Jaccard of at least 0.5.
- **What we saw (dev split only):** the gold labeler's quotes average 27.5 words (often the whole review) while the model's average 8.6. 101 of 185 gold aspects whose category the model also found were scored as misses only because the quotes differ in length. Aspect F1 on long reviews was 0.14 while review-level category F1 was 0.87.
- **v2:** match if the category is equal and the overlap coefficient (shared words divided by the shorter quote's word count) is at least 0.5. A short quote inside a long one now matches.
- **Why this is a fix and not a goalpost move:** the rule's purpose is to decide whether two labels describe the same issue. Quote length was a labeler habit, not a disagreement about the issue. The change was made on the dev split. The test split has not been scored.
- **Known weakness of v2:** if a review has two aspects in the same category, a long quote could pair with the wrong one. This is rare, and matching is one-to-one.
- The old rule stays available as `mode="jaccard"` for comparison.

## 2026-10-31: critical recall now reported two ways
- **Strict (the original definition):** a gold critical aspect counts only if the model has an aspect with the same category and it is critical. A category disagreement counts as a miss.
- **Review level (added):** a gold critical aspect counts if any aspect the model found in the same review is critical. Added because 6 of 27 human-critical cases were category disagreements (for example crash_bug versus order_execution) that say nothing about severity, and because the PM's ranking works on the highest severity in a review.
- Both numbers are always reported together. The strict number remains the pre-registered one. The review-level number was added after seeing results on the dev set, which is why it is logged here.
