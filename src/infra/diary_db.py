# infra/diary_db.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_DIARY_DB = Path("database/diary.db")

def init_diary_db(db_path: Path | str = DEFAULT_DIARY_DB) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS diaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            diary_date TEXT NOT NULL,          -- 'YYYY-MM-DD'
            title TEXT NOT NULL,
            content TEXT NOT NULL,             -- 마크다운 본문
            dialog_snapshot TEXT,              -- 일기 생성 당시 대화 스냅샷
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, diary_date)
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_diaries_session_date ON diaries(session_id, diary_date DESC)")
        conn.commit()

def upsert_diary(session_id: str, diary_date: str, title: str, content: str,
                 dialog_snapshot: Optional[str] = None,
                 db_path: Path | str = DEFAULT_DIARY_DB) -> None:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO diaries (session_id, diary_date, title, content, dialog_snapshot)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, diary_date) DO UPDATE SET
                title=excluded.title,
                content=excluded.content,
                dialog_snapshot=excluded.dialog_snapshot,
                updated_at=CURRENT_TIMESTAMP
        """, (session_id, diary_date, title, content, dialog_snapshot))
        conn.commit()

def load_diaries(session_id: str, limit: Optional[int] = None,
                 db_path: Path | str = DEFAULT_DIARY_DB) -> List[Dict[str, Any]]:
    q = """
        SELECT id, diary_date, title, content, dialog_snapshot, created_at, updated_at
        FROM diaries
        WHERE session_id = ?
        ORDER BY diary_date DESC, created_at DESC
    """
    if limit:
        q += " LIMIT ?"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        params = (session_id,) if not limit else (session_id, limit)
        cur.execute(q, params)
        rows = cur.fetchall()
        return [{k: r[k] for k in r.keys()} for r in rows]
