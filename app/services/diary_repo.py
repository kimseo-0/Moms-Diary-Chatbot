# app/services/diary_repo.py
from pathlib import Path
from typing import Optional, List
from datetime import date
from datetime import datetime as _dt
import re
import json
from pydantic import BaseModel, Field
from app.utils.db_utils import get_connection, upsert_from_model, fetch_one, fetch_all, prepare_model_sql_parts


class DiaryEntry(BaseModel):
    id: Optional[int] = None
    session_id: str
    date: str = Field(..., description="YYYY-MM-DD")
    title: Optional[str] = Field(description="일기 제목", default=None)
    content: str = Field(..., description="일기 내용")
    used_chats_json: Optional[str] = Field(description="사용된 채팅 로그(JSON 문자열)", default=None)
    used_chats: Optional[list] = Field(description="사용된 채팅 로그(파싱된 리스트)", default=None)
    created_at: Optional[str] = Field(description="생성 일시", default=None)


class DiaryRepository:
    def __init__(self, db_path: str = "storage/db/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure DB schema exists
        try:
            from app.utils.db_utils import ensure_db_initialized
            ensure_db_initialized(str(self.db_path))
        except Exception:
            pass
        # Ensure used_chats_json column exists (migration fallback)
        try:
            with get_connection(str(self.db_path)) as conn:
                conn.execute("ALTER TABLE diaries ADD COLUMN used_chats_json TEXT")
                conn.commit()
        except Exception:
            # ignore if column already exists or any other issue
            pass

    @staticmethod
    def _normalize_date_str(s: Optional[str]) -> Optional[str]:
        """Normalize various date-like strings to 'YYYY-MM-DD'.

        Accepts formats like 'YYYY-MM-DD', 'YYYY/MM/DD', 'YYYY.MM.DD',
        'YYYYMMDD', or ISO datetime 'YYYY-MM-DDTHH:MM:SS'. Returns the
        normalized 'YYYY-MM-DD' or the original value if it cannot be
        normalized.
        """
        if not s:
            return s
        s = str(s).strip()
        # If ISO datetime, take date part
        if 'T' in s:
            s = s.split('T', 1)[0]
        # Replace common separators with '-'
        s = s.replace('/', '-').replace('.', '-')
        # Compact form YYYYMMDD -> YYYY-MM-DD
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # Validate final form
        try:
            _dt.strptime(s, "%Y-%m-%d")
            return s
        except Exception:
            return s  # leave as-is if unknown format

    def save_diary(self, diary: DiaryEntry):
        """일기 저장 (upsert)"""
        with get_connection(str(self.db_path)) as conn:
            # Normalize date to 'YYYY-MM-DD'
            try:
                diary.date = self._normalize_date_str(diary.date)  # type: ignore
            except Exception:
                pass
            # 중복 체크
            cur = conn.execute(
                "SELECT id FROM diaries WHERE session_id = ? AND date = ?",
                (diary.session_id, diary.date),
            )
            row = cur.fetchone()
            if row:
                diary_id = row["id"]
                # Ensure primary key is present on the model so prepare_model_sql_parts
                # can include the PK when using exclude_none=True.
                diary.id = diary_id
                # If diary contains used_chats list, convert to JSON string for storage
                try:
                    if getattr(diary, "used_chats", None):
                        diary.used_chats_json = json.dumps(diary.used_chats, ensure_ascii=False)
                        diary.used_chats = None
                except Exception:
                    pass
                _, set_clause, values, _ = prepare_model_sql_parts(diary, pk_field="id")
                if set_clause:
                    query = f"UPDATE diaries SET {set_clause} WHERE id = ?"
                    conn.execute(query, (*values, diary_id))
                conn.commit()
            else:
                # Convert used_chats list to JSON string for storage if present
                try:
                    if getattr(diary, "used_chats", None):
                        diary.used_chats_json = json.dumps(diary.used_chats, ensure_ascii=False)
                        diary.used_chats = None
                except Exception:
                    pass
                from app.utils.db_utils import upsert_from_model
                upsert_from_model(conn, "diaries", diary, pk_field="id")

    def get_diary_by_date(self, session_id: str, target_date: str) -> Optional[DiaryEntry]:
        """특정 날짜 일기 1개 조회"""
        with get_connection(str(self.db_path)) as conn:
            # Normalize date to 'YYYY-MM-DD'
            target_date = self._normalize_date_str(target_date) or target_date
            # 날짜 기준으로 정확히 조회 (세션 + 날짜)
            cur = conn.execute(
                "SELECT * FROM diaries WHERE session_id = ? AND date = ?",
                (session_id, target_date),
            )
            diary_row = cur.fetchone()
            if not diary_row:
                return None
            d = DiaryEntry(**diary_row)
            # Parse used_chats_json into used_chats list for UI
            try:
                if d.used_chats_json:
                    d.used_chats = json.loads(d.used_chats_json)
            except Exception:
                d.used_chats = None
            return d

    def list_diaries(self, session_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[DiaryEntry]:
        """전체 또는 기간별 일기 목록 조회"""
        with get_connection(str(self.db_path)) as conn:
            if start_date and end_date:
                query = """
                    SELECT * FROM diaries
                    WHERE session_id = ?
                      AND date BETWEEN ? AND ?
                    ORDER BY date DESC
                """
                rows = conn.execute(query, (session_id, start_date, end_date)).fetchall()
            else:
                query = "SELECT * FROM diaries WHERE session_id = ? ORDER BY date DESC"
                rows = conn.execute(query, (session_id,)).fetchall()

            return [DiaryEntry(**row) for row in rows]

    def delete_diary(self, diary_id: int):
        """특정 일기 삭제"""
        with get_connection(str(self.db_path)) as conn:
            conn.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))
            conn.commit()
