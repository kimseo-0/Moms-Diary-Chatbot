import sqlite3
from typing import Dict, Any, Tuple
from pydantic import BaseModel
from app.core.pydantic_utils import safe_model_dump
from pathlib import Path


def ensure_db_initialized(db_path: str):
    """데이터베이스 파일에 필요한 테이블이 존재하는지 확인합니다.

    DB 파일 옆에 `schema.sql`(storage/db/schema.sql)이 있으면 이를 실행합니다.
    없으면 애플리케이션이 동작할 수 있도록 최소한의 `chat_logs`와 `diaries` 테이블을 생성합니다.
    이 함수는 아이디엄포턴트(idempotent)합니다.
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
            # 필요한 테이블이 존재하도록 최소한의 폴백 스키마를 적용합니다
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
    data = safe_model_dump(model, exclude_none=True)
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
    # model_dump를 우선 사용해 PK 존재 여부를 판단합니다.
    data = safe_model_dump(model, exclude_none=True)
    pk_value = data.get(pk_field)

    if pk_value is None:
        # PK가 제공되지 않음: 사용 가능한 필드로 단순 INSERT 수행
        cols = ", ".join(data.keys())
        qs = ", ".join(["?"] * len(data))
        query = f"INSERT INTO {table} ({cols}) VALUES ({qs})"
        conn.execute(query, tuple(data.values()))
    else:
        # PK가 존재함: 행이 있으면 UPDATE 시도, 없으면 INSERT 수행
        cur = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk_field} = ?", (pk_value,))
        row = cur.fetchone()
        exists = (row["COUNT(*)"] if isinstance(row, dict) else row[0]) > 0

    # 업데이트에 필요한 부분 준비 (pk_field는 제외)
        filtered, set_clause, values, _ = prepare_model_sql_parts(model, pk_field)

        if exists and set_clause:
            query = f"""
                UPDATE {table}
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE {pk_field} = ?
            """
            conn.execute(query, (*values, pk_value))
        elif not exists:
            # PK 필드를 포함한 전체 데이터를 INSERT
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
