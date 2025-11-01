# app/graphs/main_graph.py
from __future__ import annotations
from typing import Callable, Dict, Any
from langgraph.graph import StateGraph, END
from app.core.state import AgentState

# ───────────────────────────────
# Nodes
# ───────────────────────────────
from app.nodes.plan_router_node import plan_router_node
from app.nodes.urgent_triage_node import urgent_triage_node
from app.nodes.baby_smalltalk_node import baby_smalltalk_node
from app.nodes.medical_qna_node import medical_qna_node
from app.nodes.diary_node import diary_node

# Tools Registry
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

        return fn(state, **args) if args else fn(state)

    def _should_continue(state: AgentState) -> str:
        return "end" if (state.final is not None or not state.plan) else "go"

    g = StateGraph(AgentState)

    # 노드 등록
    g.add_node("router", plan_router_node)
    g.add_node("dispatch", _dispatch)

    # 진입점 및 플로우
    g.set_entry_point("router")
    g.add_edge("router", "dispatch")
    g.add_conditional_edges(
        "dispatch",
        _should_continue,
        {
            "go": "dispatch",
            "end": END
        },
    )

    return g.compile()