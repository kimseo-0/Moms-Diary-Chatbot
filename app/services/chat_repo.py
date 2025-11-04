from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from app.utils.db_utils import get_connection
from app.core.logger import get_logger

logger = get_logger(__name__)


class ChatLog(BaseModel):
    id: Optional[int] = None
    session_id: str
    role: str = Field(..., description="user | assistant | expert | system")
    text: str
    meta_json: Optional[str] = None
    created_at: Optional[str] = None


class ChatRepository:
    def __init__(self, db_path: str = "storage/db/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    # DB 스키마가 존재하는지 확인합니다
        try:
            from app.utils.db_utils import ensure_db_initialized
            ensure_db_initialized(str(self.db_path))
        except Exception:
            # 초기화 실패 시에도 계속 진행합니다; 상위 레벨 코드가 에러를 처리할 수 있습니다
            pass

    def save_message(self, message: ChatLog):
        """한 턴의 채팅을 저장합니다."""
        with get_connection(str(self.db_path)) as conn:
            query = """
                INSERT INTO chat_logs (session_id, role, text, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """
            # KST는 UTC+9입니다
            kst = timezone(timedelta(hours=9))
            conn.execute(
                query,
                (
                    message.session_id,
                    message.role,
                    message.text,
                    message.meta_json,
                    message.created_at or datetime.now(kst).isoformat(),
                ),
            )
            conn.commit()
        logger.debug("채팅 저장 완료: session=%s, role=%s", message.session_id, message.role)

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[ChatLog]:
        """최근 N개의 메시지 조회 (최신순 정렬)"""
        with get_connection(str(self.db_path)) as conn:
            query = """
                SELECT * FROM chat_logs
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            rows = conn.execute(query, (session_id, limit)).fetchall()
            return [ChatLog(**r) for r in reversed(rows)]  # 시간순으로 뒤집어서 반환

    def get_messages_by_date(self, session_id: str, target_date: str) -> List[ChatLog]:
        """특정 날짜(YYYY-MM-DD)의 메시지 조회"""
        with get_connection(str(self.db_path)) as conn:
            # created_at은 ISO 포맷(예: 2025-10-31T12:34:56+00:00)이라 앞 10글자가 날짜임
            query = """
                SELECT * FROM chat_logs
                WHERE session_id = ?
                  AND SUBSTR(created_at, 1, 10) = ?
                ORDER BY created_at ASC
            """
            rows = conn.execute(query, (session_id, target_date)).fetchall()
            return [ChatLog(**r) for r in rows]

    def get_session_messages(self, session_id: str) -> List[ChatLog]:
        """세션 전체 대화 조회"""
        with get_connection(str(self.db_path)) as conn:
            query = """
                SELECT * FROM chat_logs
                WHERE session_id = ?
                ORDER BY created_at ASC
            """
            rows = conn.execute(query, (session_id,)).fetchall()
            return [ChatLog(**r) for r in rows]

    def delete_session(self, session_id: str):
        """특정 세션 전체 대화 삭제"""
        with get_connection(str(self.db_path)) as conn:
            conn.execute("DELETE FROM chat_logs WHERE session_id = ?", (session_id,))
            conn.commit()
        logger.info("세션 전체 메시지 삭제: session=%s", session_id)

    def delete_last_message(self, session_id: str) -> bool:
        """가장 최근 채팅 메시지 1개 삭제"""
        with get_connection(str(self.db_path)) as conn:
            # 가장 최근 메시지 ID 조회
            query = """
                SELECT id FROM chat_logs
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """
            row = conn.execute(query, (session_id,)).fetchone()
            if not row:
                return False
            
            # 해당 메시지 삭제
            conn.execute("DELETE FROM chat_logs WHERE id = ?", (row["id"],))
            conn.commit()
            logger.info("가장 최근 메시지 삭제 완료: id=%s, session=%s", row["id"], session_id)
            return True
