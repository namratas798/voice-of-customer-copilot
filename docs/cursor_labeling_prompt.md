# Prompt for Cursor: label Groww reviews

Copy everything below the line into Cursor. Run it once for the dev file and once for the test file.

---

You are labeling Google Play reviews of the Groww investing app. Follow `docs/labeling_guide.md` exactly. Read it fully before starting.

## Input and output
- Input: `data/golden/dev_for_ai.jsonl` (then, in a separate run, `data/golden/test_for_ai.jsonl`). One JSON review per line with `reviewId`, `content`, `score`, `appVersion`, `date`.
- Output: `data/golden/labels_ai/dev_ai_labels.jsonl` (then `test_ai_labels.jsonl`). One JSON object per input review, in the format given in the guide. Create the folder if needed.

## Rules
1. Label **every** review exactly once. Same `reviewId`, no extras, no skips.
2. Use only the review text. The star `score` is context and must not decide a label.
3. Do not open any other file in `data/golden/` (especially `manifest.csv` and `test_blind_for_human.csv`), and do not modify the input files.
4. `quote` must be copied character for character from the review `content`. Never paraphrase it or translate it.
5. Write aspect names and categories in English, including for Hinglish reviews.
6. Work in batches of about 25 reviews, appending to the output file. Do not write a script that guesses labels with keywords. Read and judge each review yourself.
7. When unsure between two severities, choose the lower one. When unsure about a category, choose by who would need to act.
8. If you want to note an ambiguous case, add a field `"note": "<short reason>"` to that review's object. Use it only for genuinely unclear cases.

## When finished
Run the checker and fix every error it reports:

```bash
python3 -I scripts/validate_labels.py data/golden/dev_for_ai.jsonl data/golden/labels_ai/dev_ai_labels.jsonl
```

Then report: number of reviews labeled, number of validation errors (must be 0), and how many reviews have a `note`.
