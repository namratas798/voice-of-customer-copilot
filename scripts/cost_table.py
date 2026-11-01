"""Cost per 1,000 reviews from measured token use. No model calls.

Usage: python3 -I scripts/cost_table.py [out.md]

Token use per review is read from the run.json files of runs that used the current (flags) approach.
Prices are per 1 million tokens: Anthropic from the API reference cached 2026-10-06, OpenAI from the public
pricing page read on 2026-10-31. Estimates exclude hidden reasoning tokens that a provider may bill separately.
"""
import glob
import json
import sys

RUNS = [("runs/v4flags_20b_rated35", "35 rated reviews, batches of 6"), ("runs/v4flags_20b_val30", "30 fresh reviews, batches of 6"),
        ("runs/pipeline_20b_agreement108", "99 reviews incl. one-at-a-time retries")]
PRICES = [  # name, input, output
    ("gpt-oss-20b / 120b on Groq free tier", 0.0, 0.0),
    ("Claude Haiku 5.5", 0.10, 0.50), ("OpenAI gpt-6-luna", 0.10, 0.50),
    ("OpenAI gpt-6.1-terra", 1.00, 5.00),
    ("Claude Sonnet 5.5", 2.00, 10.00), ("OpenAI gpt-6.1-sol", 2.00, 10.00),
    ("Claude Opus 5.5", 4.00, 20.00),
]
lines = ["# Cost per 1,000 reviews (estimates from measured tokens)\n", "## Tokens per review, measured\n",
         "| Run | Reviews labeled | Input tokens per review | Output tokens per review |", "|---|---|---|---|"]
tot_in = tot_out = tot_n = 0
per_run = []
for path, what in RUNS:
    try:
        meta = json.load(open(path + "/run.json"))
    except OSError:
        continue
    n = meta["status"].get("ok", 0)
    if not n:
        continue
    per_run.append((what, n, meta["tokens_in"] / n, meta["tokens_out"] / n))
    lines.append("| %s | %d | %d | %d |" % (what, n, meta["tokens_in"] / n, meta["tokens_out"] / n))
    if "retries" not in what:
        tot_in += meta["tokens_in"]; tot_out += meta["tokens_out"]; tot_n += n
typ_in, typ_out = tot_in / tot_n, tot_out / tot_n
worst = per_run[-1]
lines.append("\nTypical (batches only): about %d input and %d output tokens per review. With retries: about %d and %d." %
             (typ_in, typ_out, worst[2], worst[3]))
lines += ["\n## Cost per 1,000 reviews\n", "| Model | Typical | With retries | Per month at 30 reviews a day (900) | At 10x volume | At 100x volume |",
          "|---|---|---|---|---|---|"]
for name, pi, po in PRICES:
    c = lambda i, o, n=1000: (i * pi + o * po) * n / 1e6  # noqa: E731
    typ, wst = c(typ_in, typ_out), c(worst[2], worst[3])
    lines.append("| %s | $%.2f | $%.2f | $%.2f | $%.2f | $%.2f |" % (name, typ, wst, c(typ_in, typ_out, 900), c(typ_in, typ_out, 9000), c(typ_in, typ_out, 90000)))
lines += ["\nWhat the gate saves: about 77% of reviews are skipped before any model call. Without it the typical figures above would be "
          "roughly 4 times higher, but the main benefit at this volume is less noise, not money.",
          "\nNot included: hidden reasoning tokens billed separately by some providers, prompt caching discounts, the cost of evaluation runs, "
          "and the weekly theme-merge step (about 25,000 tokens per full re-run)."]
text = "\n".join(lines) + "\n"
print(text)
if len(sys.argv) > 1:
    open(sys.argv[1], "w").write(text)
    print("saved", sys.argv[1])
