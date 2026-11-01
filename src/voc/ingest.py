"""Ingest raw Play Store JSON into SQLite. Drops identity and developer-reply fields."""
from __future__ import annotations

import json
import re
import sqlite3

HIN = set("hai nahi nhi bahut bhi kya mera mere ho hota karo kar raha rha hain h ka ki ke se mein me aur ye toh to paisa nahin accha acha bekar bakwas".split())
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def lang_script(text: str) -> str:
    if DEVANAGARI.search(text):
        return "devanagari"
    w = re.findall(r"[a-z]+", text.lower())
    if w and sum(x in HIN for x in w) / len(w) >= 0.15:
        return "hinglish"
    return "en"


def load_reviews(path: str) -> list:
    seen, rows = set(), []
    for r in json.load(open(path)):
        if r["reviewId"] in seen or not r["content"].strip():
            continue
        seen.add(r["reviewId"])
        text = r["content"].strip()
        rows.append({
            "review_id": r["reviewId"], "content": text, "score": r["score"],
            "app_version": r.get("appVersion") or "unknown", "date": r["at"][:10],
            "thumbs_up": r.get("thumbsUpCount", 0), "lang_script": lang_script(text),
        })
    return rows


SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY, content TEXT NOT NULL, score INTEGER, app_version TEXT,
  date TEXT, thumbs_up INTEGER, lang_script TEXT, gate_decision TEXT, gate_reason TEXT);
"""


def init_db(conn) -> None:
    conn.executescript(SCHEMA)


def ingest(raw_path: str, db_path: str) -> int:
    rows = load_reviews(raw_path)
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.executemany(
        "INSERT INTO reviews (review_id, content, score, app_version, date, thumbs_up, lang_script) "
        "VALUES (:review_id, :content, :score, :app_version, :date, :thumbs_up, :lang_script) "
        "ON CONFLICT(review_id) DO UPDATE SET content=excluded.content, score=excluded.score, "
        "app_version=excluded.app_version, thumbs_up=excluded.thumbs_up, lang_script=excluded.lang_script",
        rows)
    conn.commit()
    conn.close()
    return len(rows)
