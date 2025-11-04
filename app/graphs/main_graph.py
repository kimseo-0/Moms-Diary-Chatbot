from __future__ import annotations
from typing import Callable, Dict, Any
from langgraph.graph import StateGraph, END
from app.core.state import AgentState

# ───────────────────────────────
# 노드(정의)
# ───────────────────────────────
from app.nodes.plan_router_node import plan_router_node
from app.nodes.urgent_triage_node import urgent_triage_node
from app.nodes.baby_smalltalk_node import baby_smalltalk_node
from app.nodes.medical_qna_node import medical_qna_node
from app.nodes.diary_node import diary_node
from app.nodes.persona_history_node import persona_history_node
from app.nodes.persona_agent_node import persona_agent_node
from app.nodes.persona_updater_node import persona_updater_node

# 툴 레지스트리
from app.tools.tool_registry import get_all_tools


def compile_app_graph():
    """
    LangGraph 그래프를 컴파일해 반환
    """
    node_registry: Dict[str, Callable[..., AgentState]] = {
        "urgent_triage_node": urgent_triage_node,
        "baby_smalltalk_node": baby_smalltalk_node,
        "medical_qna_node":   medical_qna_node,
        "diary_node":         diary_node,
        "persona_agent_node": persona_agent_node,
        "persona_updater_node": persona_updater_node,
    }

    def _dispatch(state: AgentState) -> AgentState:
        if not state.plan:
            return state

        task = state.plan.pop(0)
        name = task.get("name")
        args: Dict[str, Any] = task.get("args", {}) or {}
        fn = node_registry.get(name)

        if fn is None:
            state.metadata.setdefault("errors", []).append(f"Unknown node: {name}")
            return state

        # persona 관련 백그라운드 트리거: persona_history_node가 이미 실행되었고
        # 아직 백그라운드가 트리거되지 않았다면 agent/updater를 비동기적으로 호출
        try:
            if state.metadata.get("history_block") and not state.metadata.get("persona_background_triggered"):
                # 호출 시 두 노드는 자체적으로 비동기 태스크를 생성하므로 여기서는 단순 호출
                try:
                    persona_agent_node(state)
                except Exception:
                    # 로그는 각 노드가 처리
                    pass
                try:
                    persona_updater_node(state)
                except Exception:
                    pass
                state.metadata["persona_background_triggered"] = True
        except Exception:
            # 방어적 코드는 문제를 기록하긴 하지만 플로우를 멈추지 않음
            state.metadata.setdefault("errors", []).append("persona background trigger failed")

        return fn(state, **args) if args else fn(state)

    def _should_continue(state: AgentState) -> str:
        return "end" if (state.final is not None or not state.plan) else "go"

    g = StateGraph(AgentState)

    # 노드 등록
    g.add_node("router", plan_router_node)
    g.add_node("persona_history", persona_history_node)
    g.add_node("dispatch", _dispatch)

    # 진입점 및 플로우: router -> persona_history (blocking) -> dispatch
    g.set_entry_point("router")
    g.add_edge("router", "persona_history")
    g.add_edge("persona_history", "dispatch")
    g.add_conditional_edges(
        "dispatch",
        _should_continue,
        {
            "go": "dispatch",
            "end": END
        },
    )

    return g.compile()