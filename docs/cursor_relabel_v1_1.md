# Prompt for Cursor: relabel the dev set under guide v1.1

Copy everything below the line into a NEW Cursor chat (not the one used before).

---

You are labeling Google Play reviews of the Groww investing app. Follow `docs/labeling_guide.md` (version 1.1) exactly. Read it fully before starting, especially the severity rules and the three new worked examples at the end of the examples section.

## Input and output
- Input: `data/golden/dev_for_ai.jsonl`. One JSON review per line with `reviewId`, `content`, `score`, `appVersion`, `date`.
- Output: `data/golden/labels_ai_v1_1/dev_ai_labels.jsonl` (create the folder). One JSON object per input review, in the format given in the guide.

## Rules
1. Label **every** review exactly once, with the same `reviewId`.
2. Label from scratch using only the review text and the guide. The star `score` is context only.
3. Do **not** open any of these folders or files, and do not copy from them: `data/golden/labels_ai/`, `data/golden/human/`, `data/golden/adjudication/`, `data/golden/manifest.csv`, `runs/`. Do not modify the input file.
4. `quote` must be copied character for character from the review `content`. Keep quotes short: the shortest span that supports the aspect, not the whole review.
5. Write aspect names and categories in English, including for Hinglish reviews.
6. Work in batches of about 25 reviews, appending to the output file. Read and judge each review yourself. Do not write a script that guesses labels with keywords.
7. Severity follows the described impact: stated rupee loss, blocked money or delayed refund is critical. A generic accusation or generic abuse with no described event is low. "App not working" with no stated impact is medium.
8. If you want to note an ambiguous case, add a field `"note": "<short reason>"` to that review's object.

## When finished
Run the checker and fix every error it reports:

```bash
python3 -I scripts/validate_labels.py data/golden/dev_for_ai.jsonl data/golden/labels_ai_v1_1/dev_ai_labels.jsonl
```

Then report: number of reviews labeled, number of validation errors (must be 0), and how many reviews have a `note`.
