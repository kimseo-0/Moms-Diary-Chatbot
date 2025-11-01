# app/nodes/urgent_triage_node.py
from __future__ import annotations
from app.core.state import AgentState
from app.core.io_payload import OutputEnvelope

def urgent_triage_node(state: AgentState) -> AgentState:
    state.final = OutputEnvelope.ok_urgent(
        text="응급이 의심돼요. 지금 바로 119 또는 가까운 응급실에 연락해주세요.",
        data={"triage": {"level": "red"}},
        source="urgent_triage_node",
    )
    return state
