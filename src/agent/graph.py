from langgraph.graph import StateGraph, START, END

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agent.state import State
from agent.nodes import baby_node, persona_node, rag_node, warning_node
from agent.router import route_agent_node, route_next
from agent.rag_tools import retrieve

# 1. 시작점
graph_builder = StateGraph(State)

# 노드 추가 (노드 이름은 엣지 연결의 목적지에 맞게 수정)
graph_builder.add_node("route_agent", route_agent_node)
graph_builder.add_node("urgent_warning", warning_node.urgent_warning_node)
graph_builder.add_node("doctor_agent", rag_node.doctor_agent_node)
graph_builder.add_node("persona_agent_node", persona_node.persona_agent_node)
graph_builder.add_node("baby_agent", baby_node.baby_agent_node) # Small Talk와 QNA 답변 포장의 최종 목적지

graph_builder.add_node("retrieve", retrieve)

# 1. 시작점
graph_builder.set_entry_point("route_agent")

# 2. 1차 조건부 엣지: route_agent -> 3가지 경로
graph_builder.add_conditional_edges(
    source="route_agent",
    path=route_next,
    path_map={
        "urgent_warning": "urgent_warning",
        "qna": "retrieve",
        "small_talk": "baby_agent",
    }
)

graph_builder.add_edge("route_agent", "persona_agent_node")
graph_builder.add_edge("retrieve", "doctor_agent")
graph_builder.add_edge("doctor_agent", "baby_agent")
graph_builder.add_edge("baby_agent", END)

compiled_graph = graph_builder.compile()