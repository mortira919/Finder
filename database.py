"""
database.py — SQLite история поисков
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict

DB_PATH = os.path.join(os.path.dirname(__file__), "leads_history.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id      TEXT NOT NULL,
            city        TEXT NOT NULL,
            country     TEXT NOT NULL,
            categories  TEXT,
            timestamp   TEXT NOT NULL,
            hot_count   INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0,
            no_site_count INTEGER DEFAULT 0,
            filepath    TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_search(job_id: str, city: str, country: str, categories: list,
                hot_count: int, total_count: int, no_site_count: int, filepath: str):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO searches
            (job_id, city, country, categories, timestamp,
             hot_count, total_count, no_site_count, filepath)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id, city, country, json.dumps(categories, ensure_ascii=False),
        datetime.now().strftime("%d.%m.%Y %H:%M"),
        hot_count, total_count, no_site_count, filepath
    ))
    conn.commit()
    conn.close()


def get_history(limit: int = 50) -> List[Dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM searches ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        d["categories"] = json.loads(d.get("categories") or "[]")
        d["file_exists"] = bool(d["filepath"] and os.path.exists(d["filepath"]))
        result.append(d)
    return result


def get_filepath_by_job(job_id: str) -> str | None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT filepath FROM searches WHERE job_id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None
