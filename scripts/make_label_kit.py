"""Build the kit for labeling a random sample of reviews with an outside model (for example ChatGPT).

Usage: python3 -I scripts/make_label_kit.py <raw_reviews.json> <out_dir> [chunk_size] [n_chunks]

Writes into <out_dir>:
  PASTE_FIRST.md        the instructions to paste once at the start of a chat (built from the guide and prompt v4)
  chunks/chunk_NN.jsonl small batches to paste one at a time (review id, text, stars only)
  sample_manifest.csv   which review is in which chunk (chunks follow one random order, so any first K chunks
                        are themselves a random sample)
Reviews that are in the golden dev/test sets or the validation set are excluded, so those stay clean.
"""
import csv
import json
import os
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from voc import extract, gate, ingest  # noqa: E402

raw, out = sys.argv[1], sys.argv[2]
chunk_size = int(sys.argv[3]) if len(sys.argv) > 3 else 12
n_chunks = int(sys.argv[4]) if len(sys.argv) > 4 else 42

excluded = set()
for f in ("data/golden/dev_for_ai.jsonl", "data/golden/test_for_ai.jsonl", "data/golden/validation/val30_inputs.jsonl"):
    p = ROOT / f
    if p.exists():
        excluded |= {json.loads(l)["reviewId"] for l in open(p)}
pool = [r for r in ingest.load_reviews(raw)
        if r["review_id"] not in excluded and gate.gate(r["content"], r["score"])[0] == "pass"]
pool.sort(key=lambda r: r["review_id"])
random.Random(42).shuffle(pool)
sample = pool[: chunk_size * n_chunks]

os.makedirs(os.path.join(out, "chunks"), exist_ok=True)
rows = []
for c in range(n_chunks):
    part = sample[c * chunk_size:(c + 1) * chunk_size]
    if not part:
        break
    with open(os.path.join(out, "chunks", "chunk_%02d.jsonl" % (c + 1)), "w") as f:
        for r in part:
            f.write(json.dumps({"reviewId": r["review_id"], "content": r["content"], "score": r["score"]},
                               ensure_ascii=False) + "\n")
            rows.append((c + 1, r["review_id"], r["date"], r["app_version"]))
with open(os.path.join(out, "sample_manifest.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["chunk", "review_id", "date", "app_version"])
    w.writerows(rows)

EXAMPLE = {"reviewId": "abc-123", "usable": True, "overall_sentiment": "negative", "aspects": [
    {"category": "payments_funds", "aspect": "withdrawal stuck", "sentiment": "negative",
     "quote": "withdrawal stuck for two days", "impact": {
         "event_described": True, "money_lost": False, "money_blocked": True, "loss_amount_stated": False,
         "order_wrong": False, "core_action_blocked": True, "workaround_mentioned": False,
         "security_or_data_issue": False}}]}

system = extract.build_system(str(ROOT), mode="flags")
paste = """# Paste this as your FIRST message in a new chat

Then paste one chunk file per message (each line is one review). Do not show the assistant any other
labels. If a reply is cut off, send the word: continue

---

""" + system + """

--- OUTPUT FORMAT (important) ---
For every review in the message, output ONE line of JSON (JSON Lines): no commentary, no code fences,
no blank lines, one JSON object per review, in the same order as the input. Each object has exactly:
reviewId, usable, overall_sentiment, aspects. Each aspect has exactly: category, aspect, sentiment, quote,
impact. `impact` has exactly the eight true/false flags listed above. Do not add a severity field.
`quote` must be copied exactly from the review text. At most 3 aspects per review; use an empty list when
usable is false.

Example of one line (shown wrapped here; yours must be a single line):
""" + json.dumps(EXAMPLE, ensure_ascii=False) + """

Reply with only: Ready. Then wait for the first chunk.
"""
with open(os.path.join(out, "PASTE_FIRST.md"), "w") as f:
    f.write(paste)
print("pool %d | excluded %d | wrote %d chunks of %d (%d reviews) to %s" %
      (len(pool), len(excluded), len(rows) // chunk_size + (1 if len(rows) % chunk_size else 0), chunk_size, len(rows), out))

# ---- file-upload version: one cleaned file with every sampled review, labeled in batches ----
with open(os.path.join(out, "all_reviews_for_upload.jsonl"), "w") as f:
    for i, r in enumerate(sample[: len(rows)], 1):
        f.write(json.dumps({"n": i, "reviewId": r["review_id"], "content": r["content"], "score": r["score"]},
                           ensure_ascii=False) + "\n")
BATCH = 20
file_prompt = """# Paste this as your FIRST message, and attach all_reviews_for_upload.jsonl to the same message

Attach only that file. Never upload the raw data file: it contains reviewer names and photos.
After each reply, save the JSON lines into a text file in data/external_labeling/returned/.
Then send the word: next

---

""" + system + """

--- HOW TO WORK THROUGH THE ATTACHED FILE ---
The attached file has one review per line (fields n, reviewId, content, score), in a fixed order.
- Label the reviews strictly in order of n, %d per reply. Start with n = 1 to %d.
- Read and judge every review yourself. Do NOT write or run code, keyword rules or scripts to produce
  labels. Never skip a review and never merge two reviews. If you cannot label one, say so in plain words.
- Start each reply with one plain line: BATCH a-b (the n values you covered). Then output the JSON
  Lines, one object per review, in the format below, with nothing else after them.
- After each reply, wait until I send the word: next
- Copy each quote exactly from the review text. Do not add a severity field.

--- OUTPUT FORMAT (important) ---
Each JSON line has exactly: reviewId, usable, overall_sentiment, aspects. Each aspect has exactly:
category, aspect, sentiment, quote, impact. `impact` has exactly the eight true/false flags listed above.
At most 3 aspects per review; use an empty list when usable is false. One line per review, no code fences.

Example of one line (shown wrapped here; yours must be a single line):
""" % (BATCH, BATCH) + json.dumps(EXAMPLE, ensure_ascii=False) + """

Reply with only: Ready. Then start with BATCH 1-%d when I say: next
""" % BATCH
with open(os.path.join(out, "PASTE_FIRST_FILE_MODE.md"), "w") as f:
    f.write(file_prompt)
print("file mode: all_reviews_for_upload.jsonl (%d reviews) + PASTE_FIRST_FILE_MODE.md" % len(rows))
