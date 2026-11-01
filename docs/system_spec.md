# System and Prompt Spec (v0.1 draft)

Implements `docs/PRD.md`. Language: Python. Model calls use the official `anthropic` SDK. Items marked **[needs sign-off]** are my defaults and you should confirm them. Prices and API rules are taken from the Claude API reference as cached on 2026-10-06, so re-check them before the benchmark.

## 1. Design principles

1. **LLM extracts, code computes.** No digit in a user-facing sentence comes from a model.
2. **Every claim is checkable.** Quotes must be exact substrings of a stored review. Citations must be real review IDs.
3. **Fail visibly.** A failed extraction, an unverifiable claim or a thin sample is shown as such, never papered over.
4. **One schema everywhere.** The labeling guide, the extractor and the validator use the same category, severity and sentiment values.
5. **Everything is versioned and cached by content.** Same review plus same prompt version plus same model gives the same stored result.

## 2. Architecture

```
raw JSON -> ingest -> reviews table
                         |
                       gate  (rules)           -> gate_decision
                         |
                    extract (LLM, batch/sync)  -> extractions, aspects tables
                         |
                  embed + cluster (per category) -> themes, theme_members
                         |
                  name themes (LLM)            -> themes.name, definition
                         |
              aggregate (code) -> metrics, regressions
                         |
             brief writer (LLM, constrained) -> briefs
                         |
                  Streamlit UI  +  chat agent (LLM + read-only tools)
```

### Repository layout
```
data/raw/            collected review files (read-only)
data/golden/         golden-set samples and labels
data/app.db          SQLite database (derived, rebuildable)
docs/                PRD, guide, specs
prompts/             versioned prompt files (extract_v1.md, name_theme_v1.md, brief_v1.md, agent_v1.md, judge_v1.md)
src/voc/
  ingest.py gate.py extract.py embed_cluster.py name_themes.py
  aggregate.py regress.py brief.py agent.py tools.py
  llm.py            single wrapper for all model calls (retries, logging, cost, refusal handling)
  validate.py       shared schema and rule checks (generalizes scripts/validate_labels.py)
evals/              eval harness and reports
app/streamlit_app.py
```

## 3. Data model (SQLite)

| Table | Key fields |
|---|---|
| `reviews` | review_id (PK), content, score, app_version (or 'unknown'), date, thumbs_up, lang_script (en / hinglish / devanagari), gate_decision, gate_reason |
| `extractions` | review_id, prompt_version, model, usable, overall_sentiment, status (ok / failed / refused), raw_json, input_tokens, output_tokens, cache_read_tokens, cost_usd, created_at |
| `aspects` | aspect_id (PK), review_id, category, aspect, sentiment, severity, quote, theme_id (nullable) |
| `themes` | theme_id (PK, stable), category, name, definition, name_version, created_at, status (active / emerging / hidden) |
| `metrics` | window_start, window_end, theme_id, count, severity_score, share, trend, priority, rating_drag, computed_at |
| `regressions` | version, baseline_version, subject (overall or theme_id), n_a, n_b, share_a, share_b, p_adj, flagged |
| `briefs` | brief_id, window, json (claims with citations), rendered_md, check_results |
| `feedback` | theme_id, action (rename / merge / hide / split), payload, created_at |
| `eval_runs` | run_id, stage, model, prompt_version, split, slice, metric, value, created_at |

`userName`, `userImage` and developer reply text are dropped at ingest and never stored.

## 4. Stage specs

### 4.1 Ingest (code)
Read raw JSON, drop duplicates by `reviewId`, drop identity and reply fields, map missing `appVersion` to `unknown`, and compute `lang_script` with the same heuristics as `scripts/draw_golden_sample.py`. Idempotent: reruns upsert.

### 4.2 Gate (code) **[needs sign-off]**
A review passes to extraction if any of the following holds:
- 8 or more words.
- 3 or more words and score of 1 to 3.
- 2 or more words and it matches the **actionable lexicon** (English and Hinglish terms such as withdraw, stuck, charge, brokerage, fraud, scam, kyc, login, otp, crash, hang, slow, order, loss, refund, deducted, nahi, paisa).

Everything else is stored with `gate_decision = skip`. Skip reasons are logged. The lexicon is tuned on the dev set only. The success metric is false-negative rate on actionable reviews of at most 2% (PRD section 10).

Honest framing: at current volume and Haiku-tier prices, the gate saves pennies. Its real benefit is less noise and fewer low-signal labels, so report it as quality and speed, not as a big cost saving.

### 4.3 Extraction (LLM)
**Model:** benchmark candidates are `claude-haiku-5-5`, `claude-sonnet-5-5` and `claude-opus-5-5`. Start development on `claude-haiku-5-5`. Use exact IDs with no date suffix.

**Request shape**
- System prompt: `prompts/extract_v1.md`, containing the wrapper below plus the full text of `docs/labeling_guide.md`. This is a long, stable prefix, so mark it for prompt caching and confirm with `usage.cache_read_input_tokens` that it is hit.
- User message: JSON with only `reviewId`, `content`, `score`. App version and date are left out because they are irrelevant to the label.
- Output: structured output (`output_config.format` with the JSON schema below). Do not use forced `tool_choice`, which newer models reject.
- Do not send `temperature`, `top_p` or `top_k`. They are rejected by the API from 2026-10-21. Determinism comes from the schema, the pinned model and the content-hash cache.
- Set `effort` explicitly on each model, and test `low` and `medium` for extraction. Haiku 5.5 and Opus 5.5 default to `medium`.
- Citations (the API feature) are incompatible with structured output and are not used. Our own quote check replaces them.

**Wrapper prompt (`extract_v1.md`, before the guide)**
```
You label Google Play reviews of the Groww investing app for a product team.
Apply the labeling guide below exactly. Use only the review text; the star
score is context and must not decide a label. Copy each quote character for
character from the review. Write aspect names in English. For Hinglish or
Devanagari reviews, keep the quote in its original script and words.
Record statements about lost money, fraud or scams as what the user claims,
never as fact. Return one JSON object that matches the schema and nothing else.

--- LABELING GUIDE (v1.0) ---
{guide text}
```

**Output schema**
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["reviewId", "usable", "overall_sentiment", "aspects"],
  "properties": {
    "reviewId": {"type": "string"},
    "usable": {"type": "boolean"},
    "overall_sentiment": {"enum": ["positive", "negative", "mixed", "neutral"]},
    "aspects": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["category", "aspect", "sentiment", "severity", "quote"],
        "properties": {
          "category": {"enum": ["order_execution","payments_funds","login_kyc_account","crash_bug","performance","ux_friction","feature_request","charges_pricing","customer_support","fraud_money_loss_claim","praise","other"]},
          "aspect": {"type": "string"},
          "sentiment": {"enum": ["positive","negative","mixed","neutral"]},
          "severity": {"enum": ["critical","high","medium","low","none"]},
          "quote": {"type": "string"}
        }
      }
    }
  }
}
```
Schema validity does not cover the rules the schema can't express (max 3 aspects, quote is a substring, severity matches sentiment). `validate.py` enforces those after every call.

**Reliability**
1. Validate. On failure, retry once with the error message appended to the user turn.
2. If it fails again, escalate to `claude-sonnet-5-5`.
3. If it still fails, store `status = failed` and show it in the UI with the review text. Never drop silently.
4. On `stop_reason = refusal`, store `status = refused` with the `stop_details` category and retry once on `claude-sonnet-5-5`. Haiku 5.5 has no server-side fallback, so this routing is done in our code. On Opus 5.5, Sonnet 5.5 and Fable 5.1 calls, enable the server-side `fallbacks` option and tell the user it's on.
5. Cache by `sha256(content + prompt_version + model + effort)`. Never re-call for a hit.

**Execution:** backfills and eval runs use the Message Batches API (asynchronous, half price). Match results by `custom_id`, never by position. The weekly job and the UI use synchronous calls.

### 4.4 Embedding and clustering (code) **[needs sign-off]**
- **Unit:** one aspect, embedded as `aspect + " | " + quote`. Only product-category aspects with negative or neutral sentiment (plus `feature_request`) are clustered. `praise` is clustered separately to tell Maya what to protect.
- **Within category:** cluster per category so every theme sits under a category. This resolves the category-vs-theme distinction from planning.
- **Embedding model:** open. Test two or three candidates on a small Hinglish similarity set built from the dev labels, and pick on measured same-theme retrieval quality. Don't assume an English-only model works on Hinglish.
- **Algorithm:** density-based clustering (e.g. HDBSCAN) with minimum cluster size 5 (decided). Noise points go to an "unclustered" pool per category and are reviewed in the UI.
- **Stable IDs:** weekly runs must not renumber themes. After each re-cluster, match new clusters to existing themes by member overlap (greater than 50% shared members keeps the old `theme_id`). New aspects between re-clusters are assigned to the nearest existing theme if cosine similarity is at least a threshold tuned on dev, otherwise left unclustered.
- User edits (merge, split, rename, hide) are stored in `feedback` and replayed after each re-cluster.

### 4.5 Theme naming (LLM)
**Model:** `claude-sonnet-5-5`. **Input:** theme category, up to 8 representative aspects with quotes (nearest to the centroid plus a few far ones for diversity). **Output (structured):** `name` (max 8 words), `definition` (one sentence), `category_agrees` (boolean), `confidence`.

Prompt rules: the name describes the problem, not blame ("Withdrawal takes more than a day", not "Groww holds your money"). It must be supported by at least two of the quotes. If the quotes don't form one coherent theme, return `coherent: false` and the theme is flagged for review.

Re-run only when more than 20% of members change.

### 4.6 Aggregation (code)
All formulas run on stored labels over a window W (default 7 days, plus a custom range).

- **Review severity for a theme:** the highest severity among that review's aspects in the theme.
- **Theme severity score:** `sum of weight(severity)` over the theme's reviews. Weights critical 8, high 4, medium 2, low 1 (decided, adjustable in the UI).
- **Trend:** `(count_W + 1) / (count_prevW + 1)`, clamped to the range 0.5 to 2.0 for the multiplier. **[needs sign-off]**
- **Priority:** `severity score x trend multiplier`.
- **Share:** theme reviews divided by all reviews in W (all reviews, not only gated ones, so percentages are not inflated).
- **Rating drag:** let `r_other` be the mean rating of reviews not in the theme. Drag is `sum over theme reviews of max(0, r_other - rating) / N_total`. It reads as "average rating would rise by about this much if these reviews were at the rating of other reviews".
- Themes with fewer than 5 reviews in W show as "emerging, low evidence".

### 4.7 Regression detection (code)
- **Comparison:** version V against the previous version V-1, and week against previous week, on (a) negative-review share (score 1 to 2) and (b) each theme's share among substantive reviews.
- **Flag only if all hold:** n of at least 30 in both groups (decided), adjusted p-value below 0.01 (Fisher exact or two-proportion test, Benjamini-Hochberg across themes), and relative increase of at least 1.5x.
- **Always display** the `unknown` version bucket beside the versioned comparison, and a note that early adopters and delayed reviews confound version attribution.
- The LLM never decides whether a regression exists. It may only explain a flagged one, using the retrieved quotes.

### 4.8 Brief writer (LLM) **[needs sign-off]**
**Model:** `claude-sonnet-5-5`.

The model receives (a) computed metrics as keyed values, (b) the verified quotes per theme with review IDs, and (c) regression flags. It writes claims as structured items:
```json
{"claims": [{"text": "Theme {{theme_7.name}} grew {{theme_7.trend_pct}} week over week ({{theme_7.count}} reviews).",
             "citations": ["<reviewId>", "<reviewId>"],
             "metric_refs": ["theme_7.trend_pct", "theme_7.count"]}]}
```
The model writes **placeholders, not digits**. A renderer substitutes real values from `metrics`.

Post-checks, which all must pass or the brief is rejected and regenerated (max 2 tries, then shown as "brief failed checks"):
1. Every `metric_ref` exists. No digits appear outside placeholders (regex).
2. Every cited review ID exists, and the claim's theme actually contains it.
3. No claim without at least one citation, except metric-only summary lines.
4. Attribution check: any sentence on fraud or money-loss uses attributed wording ("a reviewer claims"). Checked by lexicon first, then by the judge on the golden briefs.
5. Sample-size caveat is present for every theme with fewer than 30 reviews.

### 4.9 Chat agent (LLM + tools) **[needs sign-off]**
**Model:** `claude-sonnet-5-5`, effort `medium` to start. **Loop:** the SDK tool runner over custom tools, with `strict: true` on tool schemas.

**Tools (all read-only):**
| Tool | Params | Returns |
|---|---|---|
| `get_top_themes` | window, category?, platform filters, limit | theme_id, name, category, count, severity score, trend, priority |
| `get_theme_detail` | theme_id, window | definition, severity mix, version split, 5 quotes with review IDs |
| `search_reviews` | query text, filters, limit | matching review IDs with quotes (embedding or keyword search) |
| `compare_windows` | window A, window B, optional theme_id | counts and shares, with p-values where applicable |
| `get_version_stats` | version | volume, negative share, top themes, regression flags |

**System prompt rules:** you are a read-only analyst for a product manager. State a number only if a tool returned it. Cite review IDs for every quote. If tools return nothing relevant, say you don't have evidence. Attribute fraud and money-loss statements to reviewers. Say plainly when a sample is small. Do not give legal or investment advice.

**Limits:** at most 8 tool calls per question, and a token budget per session. The log stores every question, tool call and answer.

### 4.10 Safety checks (all stages)
- Identity fields never stored or displayed.
- Fraud and money-loss claims shown in a separate trust-and-risk view and always attributed.
- No output asserts that Groww caused a user's loss.
- The dev and test sets are never used in demo data without noting it.

## 5. Model and parameter policy

| Task | Default | Benchmark against | Notes |
|---|---|---|---|
| Gate, aggregation, regressions | code | none | |
| Extraction | `claude-haiku-5-5` | `claude-sonnet-5-5`, `claude-opus-5-5` | Choose the cheapest that clears the bars, per slice |
| Theme naming, brief, chat | `claude-sonnet-5-5` | `claude-opus-5-5` | |
| Eval judge | `claude-opus-5-5` | `claude-fable-5-1` for calibration | Use sparingly |
| Labeling (golden set) | different family from the evaluated model | n/a | Currently Cursor's model |

Rules for every call: pin the exact model ID, set `effort` explicitly, omit sampling parameters, log tokens, latency, cache reads and cost, and handle `refusal`. Thinking tokens count as output, so measure them.

**Cost estimate (rough, replace with measured numbers).** Assumptions: about 40 reviews a day pass the gate, about 3,500 input tokens (guide plus review) and 200 output tokens per extraction, no caching, no thinking tokens. At cached list prices:

| Model | Per day | Per month |
|---|---|---|
| `claude-haiku-5-5` | about $0.02 | about $0.5 |
| `claude-sonnet-5-5` | about $0.36 | about $11 |
| `claude-opus-5-5` | about $0.72 | about $22 |

At this volume cost is not the deciding factor. Quality per slice (especially Hinglish and severity) is. Present the cost projection at 1x, 10x and 100x volume in the case study, because the cheapest-model argument only bites at scale.

## 6. Evaluation harness

`evals/run_eval.py --stage extraction --model M --prompt-version V --split dev|test`.

**Matching rule for aspects (v2, changed 2026-10-31, see `docs/eval_changelog.md`):** a predicted aspect matches a gold aspect if the categories are equal and the overlap coefficient of the quotes (shared words divided by the shorter quote's word count) is at least 0.5. The original Jaccard rule penalized differences in quote length. Unmatched predictions are false positives, unmatched gold aspects are false negatives.

| Metric | Computed on |
|---|---|
| Usable accuracy, precision, recall | all reviews |
| Aspect precision, recall, F1 | matched pairs per rule above |
| Category macro-F1 and confusion matrix | aspect level |
| Sentiment κ | matched pairs |
| Severity weighted κ, Critical recall | matched pairs; Critical recall = gold critical aspects matched and predicted critical |
| Slice reports | by category, language script, review length, stratum |
| Gate false-negative rate | reviews labeled actionable but gated out |

Every result is written to `eval_runs` with model, prompt version and split. **Test split is touched once per release candidate**: the script refuses to run `--split test` without `--final` and records every such run.

**Judge for groundedness:** `prompts/judge_v1.md` gives the judge a claim and its cited quotes and asks whether the quotes support the claim (supported, partially, not supported). Calibrate against your own labels on 30 briefs before trusting it (target 85% agreement).

## 7. Prompt change control
Every prompt file has a version string. A change means a new version, a dev-set eval run, and a line in `docs/prompt_changelog.md` with the metric delta. No silent edits.

## 8. Build order
1. **M3a:** ingest, schema, gate, `llm.py` wrapper, extraction on dev set, first eval against Cursor's labels, plus the keyword and star-rating baselines.
2. **M3b:** embeddings and clustering, theme naming, aggregation formulas, eval of theme coherence.
3. **M4:** regression detection, brief writer with post-checks, minimal Streamlit view (brief, theme detail, releases).
4. **M5:** model benchmark, test-set run, human-labeled subset, case-study numbers.
5. **M6:** chat agent, polish, demo snapshot, writeup.

Definition of done per milestone: code runs from a clean checkout, the eval numbers are stored in `eval_runs`, and the PRD requirements it covers are ticked.

## 9. Sign-off needed
1. Gate rules (4.2).
2. Trend formula and clamp (4.6).
3. Clustering approach and similarity threshold approach (4.4).
4. Brief placeholder design (4.8). It is stricter than ordinary prompting but guarantees numbers.
5. Chat agent tools and limits (4.9).
6. Model defaults in section 5.

## 10. Implementation notes (M3b, 2026-10-31)
- **Themes use text similarity on the extractor's short English aspect phrases, not an embedding model.** Method: TF-IDF on phrase words, average-linkage clustering inside each category, merge while similarity is at least 0.2. No download needed. The phrase is already English for Hinglish reviews, which is why this is workable.
- **Threshold 0.2 was chosen on the dev split.** On 157 problem aspects: 0.35 gave 1 ranked theme and 97 singletons, 0.2 gave 5 ranked themes with sensible members, 0.1 only added a few more. Whether themes are coherent still needs a blind human check (PRD bar: at least 85% coherent).
- **Known limit:** purely lexical similarity misses synonyms ("withdrawal takes a day" versus "withdrawal pending over 24 hours" cluster only through the shared word). An embedding model is an optional upgrade, to be tested on a Hinglish similarity set before adopting.
- **Representativeness:** the dev and test samples are stratified, so shares and ranks computed on them are not the real distribution. Real rankings need the full set of gated reviews extracted.
- **Regression detection** needs at least 30 reviews per version. With the 200-review dev sample, no version pair qualifies, so nothing can be flagged. That is the intended behavior.
- Theme names are currently the most central phrase in each group. The LLM naming step (section 4.5) is optional and not built.
- Stable theme IDs across weekly re-clusters (section 4.4) are not built yet.

## 11. External labels (2026-10-31)
- To avoid waiting on Groq's free daily allowance, the product owner can label a random sample with an outside model (for example ChatGPT) using the kit in `data/external_labeling/` (`scripts/make_label_kit.py` builds it, `scripts/import_external_labels.py` checks what comes back).
- The outside model reports the same impact flags as the pipeline's extractor, so severity is derived by the same code, and labels go through the same validator. Each imported label carries a `source` field naming who produced it.
- **Provenance rule:** the pipeline's own extraction (`scripts/voc.py extract`) remains the main path and the thing evaluated. External labels are used (a) as an independent second labeler for agreement with the pipeline and (b) for the demo snapshot only if the pipeline's own full run is not finished, and the case study must say so.
- Chunks follow one random order, so any first K chunks are a random sample of the 697 eligible reviews (golden dev/test and validation reviews are excluded).
- **Deviation (2026-10-31):** the outside labeler wrote aspect names up to 16 words, longer than the pipeline's 8-word rule (the guide asks for 2 to 6). The importer accepted up to 20 words (`--max-aspect-words 20`) for these labels only. All other checks applied unchanged. Imported labels: `data/external_labeling/chatgpt_labels.jsonl`, all 504 passed.
- **Theme merge step added (2026-10-31):** after the word-matching pass, a model (`openai/gpt-oss-20b`, free tier) decides which small groups within one category mean the same underlying problem (`src/voc/theme_merge.py`, `analyze --merge-model`). Rules enforced in code: only offered groups can be merged, invented ids are dropped, forgotten groups stay as their own theme, merging never crosses categories.
- **Result on the 504-review sample (labels from the outside labeler):** themes 147 to 95, ranked themes 6 to 10, share of problem reviews inside a ranked theme 27% to 56%. Zero invented ids, one forgotten group.
- **Author's read of the 10 ranked themes (not the formal blind check):** 7 coherent, 3 slightly broad (a feature-request group that mixes US trading with fixed deposits and an education section; an account-opening group that includes a login failure; a fraud group that mixes generic accusations with a specific claim). The PRD's formal bar (at least 85% judged coherent by a human) is still open.
