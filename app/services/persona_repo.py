from __future__ import annotations
import sqlite3
from typing import Optional, Dict, Any, List
from app.core.config import config
from pathlib import Path

DB_PATH = str(config.DB_PATH)


def _conn(db_path: Optional[str] = None):
    return sqlite3.connect(db_path or DB_PATH)


def ensure_persona_tables():
    migrations_file = Path(config.ROOT_DIR) / "storage" / "db" / "migrations" / "0001_add_persona_tables.sql"
    if migrations_file.exists():
        sql = migrations_file.read_text(encoding="utf-8")
        with _conn() as conn:
            conn.executescript(sql)


def upsert_persona_summary(session_id: str, week_start: str, week_end: str, summary: str, note: Optional[str] = None) -> int:
    """주별 요약을 삽입 또는 업데이트
    """
    ensure_persona_tables()
    with _conn() as conn:
        cur = conn.execute(
            "SELECT id FROM persona_summaries WHERE session_id=? AND week_start=?",
            (session_id, week_start),
        )
        row = cur.fetchone()
        if row:
            pid = row[0]
            conn.execute(
                "UPDATE persona_summaries SET week_end=?, summary=?, note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (week_end, summary, note, pid),
            )
            return pid
        else:
            cur = conn.execute(
                "INSERT INTO persona_summaries (session_id, week_start, week_end, summary, note) VALUES (?, ?, ?, ?, ?)",
                (session_id, week_start, week_end, summary, note),
            )
            return cur.lastrowid


def get_persona_summary(session_id: str, week_start: str) -> Optional[Dict[str, Any]]:
    ensure_persona_tables()
    with _conn() as conn:
        cur = conn.execute(
            "SELECT id, session_id, week_start, week_end, summary, created_at, updated_at, note FROM persona_summaries WHERE session_id=? AND week_start=?",
            (session_id, week_start),
        )
        r = cur.fetchone()
        if not r:
            return None
        keys = ["id", "session_id", "week_start", "week_end", "summary", "created_at", "updated_at", "note"]
        return dict(zip(keys, r))


def insert_child_persona(session_id: str, persona_json: str, version: int = 1) -> int:
    ensure_persona_tables()
    with _conn() as conn:
        # find latest persona for session
        cur = conn.execute(
            "SELECT id, version FROM child_personas WHERE session_id=? ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
        if row:
            pid = row[0]
            try:
                prev_ver = int(row[1] or 1)
            except Exception:
                prev_ver = 1
            new_ver = prev_ver + 1
            conn.execute(
                "UPDATE child_personas SET persona_json=?, version=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (persona_json, new_ver, pid),
            )
            return pid
        else:
            cur = conn.execute(
                "INSERT INTO child_personas (session_id, persona_json, version) VALUES (?, ?, ?)",
                (session_id, persona_json, version),
            )
            return cur.lastrowid


def get_latest_child_persona(session_id: str) -> Optional[Dict[str, Any]]:
    ensure_persona_tables()
    with _conn() as conn:
        cur = conn.execute(
            "SELECT id, session_id, persona_json, version, created_at, updated_at FROM child_personas WHERE session_id=? ORDER BY version DESC, id DESC LIMIT 1",
            (session_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        keys = ["id", "session_id", "persona_json", "version", "created_at", "updated_at"]
        return dict(zip(keys, r))


__all__ = [
    "upsert_persona_summary",
    "get_persona_summary",
    "insert_child_persona",
    "get_latest_child_persona",
]
