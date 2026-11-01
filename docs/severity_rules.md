# Severity rules (code, v1)

Severity is derived by `src/voc/severity.py` from facts the model reports, not guessed by the model. The product owner can change a rule here and in that file without touching a prompt.

The model fills eight true/false flags per aspect:

| Flag | Meaning |
|---|---|
| `event_described` | the review describes something that happened, not only an opinion or accusation |
| `money_lost` | the user says money was lost, wrongly charged or taken |
| `money_blocked` | money, a refund or a withdrawal is stuck, blocked, delayed or missing |
| `loss_amount_stated` | a specific amount is stated |
| `order_wrong` | an order was executed wrongly or not at all, wrong price, auto square-off, or a stop loss or target failed |
| `core_action_blocked` | the user cannot trade, log in, complete KYC, deposit or withdraw |
| `workaround_mentioned` | the user says the action worked another way |
| `security_or_data_issue` | a security, privacy or data problem: wrong or leaked personal data, unauthorised access, a hacked account |

## Rules, applied in order (first match wins)

| # | Condition | Severity |
|---|---|---|
| 1 | aspect sentiment is positive or neutral, or category is praise or other | none |
| 2 | `money_lost` or `money_blocked` or `loss_amount_stated` or `order_wrong` or `security_or_data_issue` | critical |
| 3 | category is feature_request | low |
| 4 | `core_action_blocked`, no workaround | high |
| 5 | `core_action_blocked`, with a workaround | medium |
| 6 | `event_described` | medium |
| 7 | otherwise (no event described) | low |

## Where these rules come from
They encode the decisions the product owner made on 2026-10-31 after rating 40 aspects blind (see `docs/guide_changelog.md`): concrete money impact is critical, a generic accusation with no described event is low, and a vague "not working" with no stated impact is medium.

## Known limits
- The rules are only as good as the flags. If the model flags `money_lost` on a vague insult ("you robbed me"), the result is critical where the human said low. The evaluation measures flag errors through the final severity against the human ratings.
- `order_wrong` is critical on its own, even without a stated loss. This follows the human's ratings of forced square-offs and failed stop losses.
- The rules were designed on the same 40 ratings used to test them. Treat the first result as optimistic until it is checked on ratings of other reviews.
