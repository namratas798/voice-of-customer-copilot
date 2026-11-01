# Labeling Guide v1.1 (public copy, invented examples)

Version history is in `docs/guide_changelog.md`.

Used by two labelers: **the human (blind subset)** and **the AI labeler (everything else)**. Both follow these exact rules, so their agreement is meaningful.

## What you label

Each review gets:

1. `usable`: `true` or `false`
2. `aspects`: 0 to 3 items (see below)
3. `overall_sentiment`: `positive | negative | mixed | neutral`

Label only what the review says. Do not infer, and do not use the star rating to decide a label (the rating is shown for context only). Ignore everything except the review text.

### usable
`false` if the text has no product meaning: gibberish, unrelated text, a bare rating word ("good", "nice app"), or only abuse with no claim.
If `usable=false`, `aspects` is empty.
A short review is usable if it names a problem or feature ("withdraw stuck", "add dark mode").

### aspects (max 3)
One aspect per distinct thing the user talks about. If there are more than 3, keep the 3 with the highest severity (ties: first mentioned).

Each aspect has:

| Field | Values |
|---|---|
| `category` | one of the 12 categories below |
| `aspect` | 2 to 6 words naming the specific thing, e.g. "withdrawal delay", "stop loss not triggering" |
| `sentiment` | `positive | negative | mixed | neutral` (about this aspect only) |
| `severity` | `critical | high | medium | low | none` (use `none` for positive or neutral aspects) |
| `quote` | exact words copied from the review that support the aspect, no paraphrase |

## Categories

| Category | Use when the review is about | Owner |
|---|---|---|
| `order_execution` | placing, executing, modifying or cancelling orders; stop loss; MTF; order status | Trading eng |
| `payments_funds` | deposits, withdrawals, UPI, bank linking, refunds, wallet balance | Payments |
| `login_kyc_account` | login, OTP, KYC, account opening or closure, PAN/Aadhaar | Identity |
| `crash_bug` | crashes, freezes, wrong values, features not working as designed | Eng |
| `performance` | slowness, lag, load times, delays when the app does work | Eng/platform |
| `ux_friction` | confusing, missing or changed UI, layout, charts, navigation, readability | Design |
| `feature_request` | asks for something that does not exist yet | Roadmap |
| `charges_pricing` | brokerage, fees, taxes, DP charges, AMC, hidden or high charges | Pricing |
| `customer_support` | support responsiveness, quality, tickets | Support ops |
| `fraud_money_loss_claim` | the user claims Groww itself took, lost, froze or mishandled their money, or calls Groww a scam | Trust and risk |
| `praise` | general or specific positive feedback | None |
| `other` | non-actionable: generic abuse, market opinions, unrelated | None |

`customer_support`, `fraud_money_loss_claim`, `praise` and `other` are non-product categories. They never enter the product fix list.

### Disambiguation rules
- **Crash vs performance:** freezing or crashing is `crash_bug`. Slow but working is `performance`. "Hangs during trading" is `crash_bug`.
- **Bug vs UX:** a thing that is broken is `crash_bug`. A thing that works but is confusing, missing or changed is `ux_friction`.
- **Fraud claim vs the rest:** use `fraud_money_loss_claim` only when the claim is about Groww's conduct ("Groww took my money", "scam broker"). A general opinion about the market ("options trading is a scam") is `other`. If the same review also describes a concrete failure (e.g. a stuck withdrawal), also add that aspect in its own category.
- **Support vs the problem:** if the review is mainly "my KYC is stuck and support does not help", label two aspects: `login_kyc_account` and `customer_support`.
- **Feature request:** wishes and asks ("add my bank for deposits") are `feature_request`. Complaints about something that used to exist and was removed are `ux_friction`.
- **Charges:** complaining a fee is high is `charges_pricing`. Claiming an unauthorised deduction is `fraud_money_loss_claim`.

## Severity rubric (per aspect, negative aspects only)

Judge the severity of the problem as described. Do not judge how angry the user is.

| Level | Meaning | Example |
|---|---|---|
| `critical` | money is moved wrongly, lost, or blocked (including a stated rupee loss, blocked funds, or a delayed refund), an order executed incorrectly, or an account, security or data problem | "My margin position was sold automatically and I lost 40,000 rupees" |
| `high` | a core action (trade, login, KYC, withdraw) fails and there is no stated workaround | "The exit button did nothing and I could not close my trade" |
| `medium` | degraded or slow experience, or a workaround exists | "The chart shows an old price until I reopen the screen" |
| `low` | cosmetic, minor or a wish | "Please make the numbers a bit bigger" |

Time-sensitive rule: a failure that blocks acting in the market during trading hours is at least `high`.

**Described impact decides severity (v1.1).**
- Concrete money impact is `critical`: a stated rupee loss, money blocked, or a refund delayed (for example an IPO refund). Do not stop at `high` just because the user got the money back later or the amount is small.
- A complaint with no described event is `low`: a generic accusation ("scam app", "thief"), or generic abuse about support ("worst customer support") with no amount, transaction, blocked money or failed action. Its category does not change this.
- A problem described only vaguely ("app not working") with no stated impact on trading or on a core action is `medium`.
- Otherwise pick the level that the described impact supports. Do not average, and do not raise or lower a level because of how angry the wording is.

## Worked examples (invented)

These reviews were written for this guide. They illustrate the rules above.

**1. `demo-1` (1★)** "The platform closed my intraday position on its own and my stop loss never ran as I set it. This is a scam."
- aspect "position closed automatically", `order_execution`, negative, `critical`
- aspect "scam allegation", `fraud_money_loss_claim`, negative, `low` (a generic accusation with no event of its own)
- overall: negative

**2. `demo-2` (1★)** "Trading is a trap that makes ordinary people lose money."
- aspect "opinion about trading", `other`, negative, `none`
- usable: true, overall: negative. An opinion about the market, not a claim about the app.

**3. `demo-3` (1★)** "Too slow when I try to place a trade during market hours."
- aspect "slow for trading", `performance`, negative, `high` (trading context)
- overall: negative

**4. `demo-4` (5★)** "Please make the numbers bigger, they are hard to read. Everything else is easy to find."
- aspect "numbers too small", `ux_friction`, negative, `low`
- aspect "easy to navigate", `praise`, positive, `none`
- overall: mixed

**5. `demo-5` (4★)** "When will my savings bank be supported for adding funds?"
- aspect "bank not supported for deposits", `feature_request`, neutral, `none` (a plain question; if framed as a complaint, use negative and `low`)
- overall: neutral

**6. `demo-6` (1★)** "Worst app, do not install."
- aspect "generic abuse", `other`, negative, `none`
- overall: negative. No claim, so only an `other` aspect.

**7. Hinglish, `demo-7` (1★)** "Mere paise teen din se atke hue hain, withdrawal nahi ho raha."
- aspect "money stuck for three days", `payments_funds`, negative, `critical`
- overall: negative. Label in English. Keep the `quote` in the original script and words.

**8. `demo-8` (1★)** "Scam app, full of fraud."
- aspect "scam allegation", `fraud_money_loss_claim`, negative, `low` (generic accusation, no described event)
- overall: negative

**9. `demo-9` (1★)** "My IPO refund of 4,500 rupees has not come back after a week. This blocked my money."
- aspect "IPO refund delayed", `payments_funds`, negative, `critical` (blocked money and a stated amount)
- overall: negative

**10. `demo-10` (1★)** "Support is the worst I have seen."
- aspect "poor customer support", `customer_support`, negative, `low` (generic, no described event)
- overall: negative

## Output format (one JSON object per review)

```json
{
  "reviewId": "...",
  "usable": true,
  "overall_sentiment": "negative",
  "aspects": [
    {"category": "order_execution", "aspect": "stop loss not triggering", "sentiment": "negative", "severity": "critical", "quote": "stoploss also not triggering"}
  ]
}
```

Validation rules (checked automatically):
- `category` and `severity` must be from the lists above.
- `quote` must be a substring of the review text.
- At most 3 aspects. Empty `aspects` if `usable` is false.
- `severity` is `none` for positive or neutral aspects.

## Ground rules
- Do not use the developer reply (it is boilerplate and is not in your input).
- Do not use userName or any identity. They are removed.
- Never state a fraud or money-loss claim as fact. Label it as a claim by the user.
- If you are unsure, pick the category by who would need to act, and set severity by the described impact (see the severity rules).
