# Voice of Customer Copilot

Turns App reviews into prioritized, evidence-backed decisions for a PM. See `docs/PRD.md` and `docs/system_spec.md`.

Check it out here: https://voice-of-customer-copilot-f6achlhlvutr6xyye3sdms.streamlit.app/

## Setup
Python 3.12 virtual environment lives in `.venv` (created with uv). Run everything from the project root with `.venv/bin/python -I`.

API key: create a file named `.env` in the project root containing one line, `ANTHROPIC_API_KEY=your-key`. Never commit or share it. The pipeline reads it only for the `extract` command.

## Commands
```bash
.venv/bin/python -I -m unittest discover -s tests            # unit tests
.venv/bin/python -I scripts/voc.py ingest data/raw/<file>.json
.venv/bin/python -I scripts/voc.py baseline --kind keywords --input data/golden/dev_for_ai.jsonl --out runs/baseline_kw_dev
.venv/bin/python -I scripts/voc.py extract --input data/golden/dev_for_ai.jsonl --out runs/dev_gptoss120b --dry-run
.venv/bin/python -I scripts/voc.py extract --input data/golden/dev_for_ai.jsonl --out runs/dev_gptoss120b   # Groq, batches of 10
.venv/bin/python -I scripts/voc.py eval --split dev --pred runs/dev_gptoss120b/labels.jsonl
```

Groq free tier notes (measured on 2026-10-31 for `openai/gpt-oss-120b`): 8,000 tokens per minute, and the docs list 200,000 tokens per day. A batch of 10 reviews uses about 5,000 tokens, so a 200-review run is about 20 calls and roughly 100K tokens. Keep `--workers 1`. Use `GROQ_API_KEY` in `.env`.

## Labeling with an outside model (optional)
1. Open `data/external_labeling/PASTE_FIRST.md`, copy everything below the first `---` line, and paste it as the first message of a new chat. Wait for "Ready."
2. Paste one `data/external_labeling/chunks/chunk_NN.jsonl` per message. Save each reply as a text file in `data/external_labeling/returned/`.
3. Check and import:
```bash
.venv/bin/python -I scripts/import_external_labels.py --chunks data/external_labeling/chunks --returned data/external_labeling/returned --out data/external_labeling/chatgpt_labels.jsonl --labeler "ChatGPT (model name)"
```

## The app (Streamlit)
```bash
.venv/bin/streamlit run app/streamlit_app.py
```
Opens at http://localhost:8501. It reads `app/snapshot.json`, a frozen snapshot, so every page except "Try it on a review" loads instantly and needs no model key. To rebuild the snapshot from labels:
```bash
.venv/bin/python -I scripts/build_snapshot.py --reviews data/external_labeling/sample_inputs.jsonl --labels data/external_labeling/chatgpt_labels.jsonl --out app/snapshot.json
```
"Try it on a review" calls the free Groq model and needs `GROQ_API_KEY` (in `.env` locally, or in the host's secrets when deployed). It allows 5 tries per session and handles the free daily limit with a plain message. Never commit `.env`.

## Explaining the numbers
See `docs/how_reliable_explained.md` for how every figure on the "How reliable is this?" page is measured, with formulas, commands to recompute each number, and the honest limits.

## Publishing the app (public demo with invented reviews)
The public version never contains real reviews. If `app/snapshot.json` (real data) is missing, the app opens `app/demo_snapshot.json`, 420 reviews written for a fictional app. To preview the demo on your own machine: `VOC_DEMO=1 .venv/bin/streamlit run app/streamlit_app.py`.

Before pushing anything to a public repository, both of these must pass:
```bash
.venv/bin/python -I scripts/public_check.py     # no real review text in anything that would be public
.venv/bin/python -I scripts/privacy_scan.py     # no keys, key file owner-only, .gitignore covers the private files
```
Steps on Streamlit Community Cloud, as I understand them (check their current docs): put the repository on GitHub, create a new app pointing at `app/streamlit_app.py`, and add your key in the app's Secrets as `GROQ_API_KEY = "..."`. The key must never be in the code or the repository. The live "Try it on a review" feature allows 5 tries per visitor and 40 per day in total, to protect the free allowance.
