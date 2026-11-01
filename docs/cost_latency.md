# Cost per 1,000 reviews (estimates from measured tokens)

## Tokens per review, measured

| Run | Reviews labeled | Input tokens per review | Output tokens per review |
|---|---|---|---|
| 35 rated reviews, batches of 6 | 35 | 730 | 276 |
| 30 fresh reviews, batches of 6 | 30 | 931 | 254 |
| 99 reviews incl. one-at-a-time retries | 99 | 1217 | 205 |

Typical (batches only): about 823 input and 266 output tokens per review. With retries: about 1217 and 205.

## Cost per 1,000 reviews

| Model | Typical | With retries | Per month at 30 reviews a day (900) | At 10x volume | At 100x volume |
|---|---|---|---|---|---|
| gpt-oss-20b / 120b on Groq free tier | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 |
| Claude Haiku 5.5 | $0.22 | $0.22 | $0.19 | $1.94 | $19.39 |
| OpenAI gpt-6-luna | $0.22 | $0.22 | $0.19 | $1.94 | $19.39 |
| OpenAI gpt-6.1-terra | $2.15 | $2.25 | $1.94 | $19.39 | $193.92 |
| Claude Sonnet 5.5 | $4.31 | $4.49 | $3.88 | $38.78 | $387.84 |
| OpenAI gpt-6.1-sol | $4.31 | $4.49 | $3.88 | $38.78 | $387.84 |
| Claude Opus 5.5 | $8.62 | $8.98 | $7.76 | $77.57 | $775.69 |

What the gate saves: about 77% of reviews are skipped before any model call. Without it the typical figures above would be roughly 4 times higher, but the main benefit at this volume is less noise, not money.

Not included: hidden reasoning tokens billed separately by some providers, prompt caching discounts, the cost of evaluation runs, and the weekly theme-merge step (about 25,000 tokens per full re-run).
