from pathlib import Path
from typing import Optional, List
from datetime import date
from datetime import datetime as _dt
import re
import json
from pydantic import BaseModel, Field
from app.utils.db_utils import get_connection, upsert_from_model, fetch_one, fetch_all, prepare_model_sql_parts
from app.core.logger import get_logger

logger = get_logger(__name__)


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
    # DB 스키마가 존재하는지 확인합니다
        try:
            from app.utils.db_utils import ensure_db_initialized
            ensure_db_initialized(str(self.db_path))
        except Exception:
            pass
    # 참고: schema.sql은 이미 used_chats_json을 포함합니다. 초기화 시점에
    # ALTER TABLE을 수행하기보다는 migrations(storage/db/migrations/*.sql)를 신뢰하세요.

    @staticmethod
    def _normalize_date_str(s: Optional[str]) -> Optional[str]:
        """다양한 날짜 형식을 'YYYY-MM-DD'로 정규화합니다.

        'YYYY-MM-DD', 'YYYY/MM/DD', 'YYYY.MM.DD', 'YYYYMMDD' 또는
        ISO datetime('YYYY-MM-DDTHH:MM:SS') 등을 처리합니다. 변환이
        불가능하면 원래 값을 반환합니다.
        """
        if not s:
            return s
        s = str(s).strip()
    # ISO datetime이면 날짜 부분만 취합니다
        if 'T' in s:
            s = s.split('T', 1)[0]
    # 일반적인 구분자('/', '.')를 '-'로 바꿉니다
        s = s.replace('/', '-').replace('.', '-')
    # 압축 형식 YYYYMMDD -> YYYY-MM-DD 변환
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 최종 형식 검증
        try:
            _dt.strptime(s, "%Y-%m-%d")
            return s
        except Exception:
            return s  # 알 수 없는 형식이면 그대로 반환

    def save_diary(self, diary: DiaryEntry):
        """일기 저장 (upsert)"""
        logger.debug("save_diary 호출: session=%s, date=%s", getattr(diary, 'session_id', None), getattr(diary, 'date', None))
        with get_connection(str(self.db_path)) as conn:
            # 날짜를 'YYYY-MM-DD'로 정규화
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
                # prepare_model_sql_parts가 exclude_none=True일 때 PK를 포함할 수 있도록
                # 모델에 기본키가 있는지 보장합니다.
                diary.id = diary_id
                # diary에 used_chats 리스트가 있으면 저장을 위해 JSON 문자열로 변환
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
                    logger.info("일기 업데이트: id=%s, session=%s", diary_id, diary.session_id)
                conn.commit()
            else:
                # used_chats 리스트가 있으면 저장용으로 JSON 문자열로 변환
                try:
                    if getattr(diary, "used_chats", None):
                        diary.used_chats_json = json.dumps(diary.used_chats, ensure_ascii=False)
                        diary.used_chats = None
                except Exception:
                    pass
                from app.utils.db_utils import upsert_from_model
                upsert_from_model(conn, "diaries", diary, pk_field="id")
                logger.info("일기 신규 저장: session=%s, date=%s", diary.session_id, diary.date)

    def get_diary_by_date(self, session_id: str, target_date: str) -> Optional[DiaryEntry]:
        """특정 날짜 일기 1개 조회"""
        with get_connection(str(self.db_path)) as conn:
            # 날짜를 'YYYY-MM-DD'로 정규화
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
            # UI 용도로 used_chats_json을 used_chats 리스트로 파싱
            try:
                if d.used_chats_json:
                    d.used_chats = json.loads(d.used_chats_json)
            except Exception:
                d.used_chats = None
            return d
        logger.debug("get_diary_by_date 조회: session=%s, date=%s, result_id=%s", session_id, target_date, d.id if d else None)

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
        logger.debug("list_diaries 조회: session=%s, start=%s, end=%s, count=%d", session_id, start_date, end_date, len(rows))

    def delete_diary(self, diary_id: int):
        """특정 일기 삭제"""
        with get_connection(str(self.db_path)) as conn:
            conn.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))
            conn.commit()
        logger.info("일기 삭제 완료: id=%s", diary_id)
