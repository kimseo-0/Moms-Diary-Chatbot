# infra/chat_db.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = Path("database/chat.db")

def init_chat_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """
    1) 디비가 없으면 생성하고, messages 테이블을 준비한다.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")
        conn.commit()


def save_message(session_id: str, role: str, content: str,
                 db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """
    2) 특정 session_id로 (role, content) 메시지를 저장한다.
       role: 'user' | 'assistant' | 'system'
    """
    if role not in ("user", "assistant", "system"):
        raise ValueError("role must be one of: 'user', 'assistant', 'system'")

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


def load_messages(session_id: str,
                  db_path: Path | str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    3) 특정 session_id의 모든 메시지를 시간순으로 로드한다.
       반환: [{'role':'user'|'assistant'|'system', 'content':'...'}, ...]
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

def load_messages_by_date(session_id: str, date_str: str,
                          db_path: Path | str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    date_str: 'YYYY-MM-DD' (서버의 로컬 타임존 기준으로 DATE(created_at) 매칭)
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE session_id = ?
              AND DATE(created_at) = DATE(?)
            ORDER BY id ASC
            """,
            (session_id, date_str),
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in rows]