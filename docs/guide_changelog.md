# Labeling guide changelog

## v1.1 (2026-10-31)
**Evidence.** On the dev split, the model (gpt-oss-120b, prompt v1) caught 11 of the 27 aspects a human rated critical (41%) against a bar of 90%. The human (the product owner) rated 40 aspects blind of both labelers: 28 that Cursor had called critical plus 12 non-critical controls. Human and Cursor agreed exactly on 32 of 40 (80%). Ratings are in `data/golden/human/severity_ratings_dev40.csv`.

**What the disagreements showed**
- Generic accusations with no described event (rows 1, 23, 40): human rated low, Cursor rated critical.
- Delayed refunds and stated rupee losses (rows 18, 33): human rated critical, Cursor and the model rated high.
- Generic support complaints and vague "not working" (rows 13, 15): human rated lower than Cursor.
- The v1.0 tie-break "when in doubt, choose the lower level" likely caused the model's low critical recall.
- Known inconsistency: the human rated row 28 (a broad profit-taking accusation) critical while rating three similar rows low. The new rule makes that explicit.

**Changes (accepted by the product owner)**
1. A fraud or scam claim with no described event is `low`.
2. A stated rupee loss, blocked money or a delayed refund is `critical`.
3. "When in doubt, choose the lower level" is replaced by "described impact decides severity".
4. Critical definition now names stated losses, blocked funds and delayed refunds. Three worked examples added.

**Consequence.** Gold labels produced under v1.0 are not consistent with v1.1 on severity. The dev set is relabeled under v1.1 before the next scoring round. The test split is relabeled under v1.1 before it is scored. Neither split's v1.0 labels are overwritten (`data/golden/labels_ai/`).

## v1.0 (2026-10-31)
Initial guide.
