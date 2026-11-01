"""Rule-based gate: decides which reviews go to the LLM. See docs/system_spec.md 4.2."""
from __future__ import annotations

import re
import sqlite3

from .ingest import lang_script

LEXICON = re.compile(
    r"\b(withdraw\w*|stuck|charg\w*|brokerage|fraud\w*|scam\w*|kyc|login|log in|otp|crash\w*|"
    r"hang\w*|hung|slow\w*|order\w*|loss\w*|lost|refund\w*|deduct\w*|nahi|nhi|nahin|paisa|paise|"
    r"error\w*|bug\w*|glitch\w*|not working|cheat\w*|fake|block\w*|freez\w*|frozen|hack\w*|"
    r"support|ipo|upi|bank|margin|mtf|sip|kharab|bekar|bakwas|pending|fail\w*|delay\w*)\b",
    re.I)


def gate(content: str, score: int):
    """Return (decision, reason). decision is 'pass' or 'skip'."""
    n = len(content.split())
    if n >= 8:
        return "pass", "len>=8"
    if n >= 3 and score <= 3:
        return "pass", "low_score_len>=3"
    if n >= 2:
        m = LEXICON.search(content)
        if m:
            return "pass", "lexicon:" + m.group(0).lower()
        if lang_script(content) != "en":
            return "pass", "non_english_script"
    return "skip", "short_no_signal"


def apply_gate(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT review_id, content, score FROM reviews").fetchall()
    counts = {"pass": 0, "skip": 0}
    for rid, content, score in rows:
        d, why = gate(content, score)
        counts[d] += 1
        conn.execute("UPDATE reviews SET gate_decision=?, gate_reason=? WHERE review_id=?", (d, why, rid))
    conn.commit()
    conn.close()
    return counts
