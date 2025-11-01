# app/nodes/urgent_triage_node.py
from __future__ import annotations
from app.core.state import AgentState
from app.core.io_payload import OutputEnvelope
from app.core.logger import get_logger

logger = get_logger(__name__)


def urgent_triage_node(state: AgentState) -> AgentState:
    logger.warning("urgent_triage_node 호출 - 응급 가능성 판단, 세션=%s", state.input.session_id)
    state.final = OutputEnvelope.ok_urgent(
        text="응급이 의심돼요. 지금 바로 119 또는 가까운 응급실에 연락해주세요.",
        data={"triage": {"level": "red"}},
        source="urgent_triage_node",
    )
    logger.info("urgent_triage_node 응답 준비 완료: source=urgent_triage_node, session=%s", state.input.session_id)
    return state
