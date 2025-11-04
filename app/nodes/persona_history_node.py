"""
persona_history_node

동기 노드: 현재 대화 처리 전에 실행되어 history_block을 state.metadata['history_block']에 저장합니다.

간단하고 직관적인 구현으로 시작합니다. 실제 recent chats 소스는 나중에 chat_repo로 연결하세요.
"""
from __future__ import annotations
from typing import Any
from app.core.state import AgentState
from app.tools.persona_tools import get_or_build_history_block
from app.core.logger import get_logger

logger = get_logger(__name__)


def persona_history_node(state: AgentState) -> AgentState:
    """
    AgentState를 받아 history_block을 생성/조회해 state.metadata에 저장하고 반환한다.
    blocking(동기)으로 실행
    """
    session_id = state.session_id
    # target_date는 간단히 현재 날짜 문자열을 사용하도록 함
    # 실제는 state.input.payload에 포함된 타임스탬프를 사용할 수 있음
    # InputPayload.metadata is a Pydantic model (InputMetadata), access attributes directly
    target_date = None
    try:
        if state.input and state.input.payload and state.input.payload.metadata:
            target_date = getattr(state.input.payload.metadata, "date", None)
    except Exception:
        target_date = None
    if not target_date:
        try:
            from zoneinfo import ZoneInfo
            from datetime import datetime

            target_date = datetime.now(tz=ZoneInfo("Asia/Seoul")).date().isoformat()
        except Exception:
            from datetime import datetime, timezone, timedelta

            kst = timezone(timedelta(hours=9))
            target_date = datetime.now(tz=kst).date().isoformat()

    logger.info("persona_history_node: building history for session=%s date=%s", session_id, target_date)

    history_block = get_or_build_history_block(session_id, target_date)
    state.metadata["history_block"] = history_block
    logger.debug("persona_history_node: history_block attached for session=%s", session_id)
    return state


__all__ = ["persona_history_node"]
