# app/services/db_utils.py
import sqlite3
from typing import Dict, Any, Tuple
from pydantic import BaseModel
from pathlib import Path


def ensure_db_initialized(db_path: str):
    """Ensure the database file has required tables.

    If a `schema.sql` file exists next to the DB (storage/db/schema.sql), run it.
    Otherwise create minimal `chat_logs` and `diaries` tables so the app can operate.
    This function is idempotent.
    """
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    schema_file = p.parent / "schema.sql"

    conn = sqlite3.connect(str(p))
    try:
        if schema_file.exists():
            with schema_file.open("r", encoding="utf-8") as fh:
                sql = fh.read()
            if sql.strip():
                conn.executescript(sql)
        else:
            # minimal fallback schema to ensure required tables exist
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_logs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  text TEXT NOT NULL,
                  meta_json TEXT,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS diaries (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT NOT NULL,
                  date TEXT NOT NULL,
                  title TEXT,
                  content TEXT NOT NULL,
                  tags_json TEXT,
                  week INTEGER,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE (session_id, date)
                );
                """
            )
    finally:
        conn.commit()
        conn.close()


def dict_factory(cursor, row):
    """sqlite3.Row -> dict 변환"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    return conn

def prepare_model_sql_parts(model: BaseModel, pk_field: str = "id") -> Tuple[Dict[str, Any], str, list, Any]:
    """모델에서 업데이트/삽입용 컬럼, 값, PK 추출
    - model.model_fields 기준으로 안전한 컬럼만 사용
    - exclude_none=True 로 None 필드 제거
    - set_clause, values, pk_value 반환
    """
    data = model.model_dump(exclude_none=True)
    if pk_field not in data:
        raise ValueError(f"Primary key field '{pk_field}' missing in data")

    valid_cols = list(model.__class__.model_fields.keys())
    filtered = {k: v for k, v in data.items() if k in valid_cols and k != pk_field}
    pk_value = data[pk_field]

    if not filtered:
        return {}, "", [], pk_value

    set_clause = ", ".join([f"{k} = ?" for k in filtered.keys()])
    values = list(filtered.values())
    return filtered, set_clause, values, pk_value


def upsert_from_model(conn: sqlite3.Connection, table: str, model: BaseModel, pk_field: str = "session_id"):
    """
    Pydantic 모델 기반 동적 UPSERT (INSERT or UPDATE)
    """
    # Use model_dump first so we can decide whether PK is present.
    data = model.model_dump(exclude_none=True)
    pk_value = data.get(pk_field)

    if pk_value is None:
        # No PK provided: perform a simple INSERT of available fields
        cols = ", ".join(data.keys())
        qs = ", ".join(["?"] * len(data))
        query = f"INSERT INTO {table} ({cols}) VALUES ({qs})"
        conn.execute(query, tuple(data.values()))
    else:
        # PK present: attempt update if row exists, otherwise insert
        cur = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk_field} = ?", (pk_value,))
        row = cur.fetchone()
        exists = (row["COUNT(*)"] if isinstance(row, dict) else row[0]) > 0

        # Prepare update parts (exclude pk_field itself)
        filtered, set_clause, values, _ = prepare_model_sql_parts(model, pk_field)

        if exists and set_clause:
            query = f"""
                UPDATE {table}
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE {pk_field} = ?
            """
            conn.execute(query, (*values, pk_value))
        elif not exists:
            # Insert full data (including pk_field)
            cols = ", ".join(data.keys())
            qs = ", ".join(["?"] * len(data))
            query = f"INSERT INTO {table} ({cols}) VALUES ({qs})"
            conn.execute(query, tuple(data.values()))

    conn.commit()


def fetch_one(conn: sqlite3.Connection, table: str, pk_field: str, pk_value: Any):
    """단일 row 조회"""
    cur = conn.execute(f"SELECT * FROM {table} WHERE {pk_field} = ?", (pk_value,))
    row = cur.fetchone()
    return row if row else None


def fetch_all(conn: sqlite3.Connection, table: str, where: str = "", params: tuple = ()):
    """모든 row 조회"""
    query = f"SELECT * FROM {table}"
    if where:
        query += f" WHERE {where}"
    cur = conn.execute(query, params)
    return cur.fetchall()
