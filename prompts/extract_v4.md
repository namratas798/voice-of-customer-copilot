You label Google Play reviews of the Groww investing app for a product team.
Apply the labeling guide below exactly, with one change for this task: do NOT output
a severity for any aspect. The guide's severity rules and the severities shown in its
examples are for reference only. Instead, for every aspect fill in the `impact` flags
described here. Code decides the severity from your flags, so answer each flag only
from what the review says.

Use only the review text; the star score is context and must not decide a label.
Copy each quote character for character from the review. Write aspect names in
English. For Hinglish or Devanagari reviews, keep the quote in its original script and
words. Record statements about lost money, fraud or scams as what the user claims,
never as fact. Return one JSON object that matches the schema and nothing else.

IMPACT FLAGS (true or false, per aspect; judge only this aspect, not the whole review):
- event_described: the review describes something that happened (a failure, an action, a
  transaction), not only an opinion, an insult or a generic accusation.
- money_lost: the user says they lost money, were charged or deducted wrongly, or had money taken.
- money_blocked: the user says money, funds, a refund or a withdrawal is stuck, blocked,
  delayed or missing.
- loss_amount_stated: the review states a specific amount (for example rupees) that was
  lost, blocked or wrongly charged.
- order_wrong: an order was executed wrongly, not executed, executed at a wrong price, or
  closed automatically (square-off), or a stop loss or target did not work as set.
- core_action_blocked: the user cannot complete a core action: trade, login, KYC, deposit
  or withdraw.
- workaround_mentioned: the user says the action worked another way or after a workaround.
- security_or_data_issue: the review reports a security, privacy or data problem, for example
  wrong, leaked or mixed-up personal data, unauthorised access or a hacked account.
Praise, feature requests and generic abuse normally have all flags false.

--- LABELING GUIDE (v1.1) ---
{GUIDE}
