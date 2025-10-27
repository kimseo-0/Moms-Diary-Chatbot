from typing import Literal
from langchain_core.prompts import ChatPromptTemplate

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.state import State, log
from agent.models import llm_ctrl

routing_system = (
"""
    당신은 사용자 질문의 의도를 분석하여 다음 기능 노드를 결정하는 라우터입니다.

    [판단 기준 및 출력 규칙]
    - 'urgent_warning': 심한 통증, 출혈, 고열 등 **즉시 전문의 상담이나 병원 방문이 필요할 수 있는 심각한 증상** 질문일 경우.
    - 'qna_agent': 임신, 건강, 전문 지식 관련 질문일 경우.
    - 'small_talk_agent': 단순 인사, 잡담, 감정 교류 등 일상 대화일 경우.
    
    다른 설명 없이, **반드시 셋 중 하나의 라우팅 키('urgent_warning', 'qna', 'small_talk')만 출력**해야 합니다.
    """
)

def route_agent_node(state : State) -> State:
    # 1. 최신 사용자 메시지 추출
    user_message_object = state["messages"][-1]
    user_input = user_message_object.content 

    prompt = ChatPromptTemplate.from_messages([
        ("system", routing_system),
        ("user", f"사용자 질문: {user_input}")
    ])
    
    # 2. LLM 호출 및 라우팅 키 추출
    res = llm_ctrl.invoke(prompt.format_messages())
    routing_key = res.content.strip().lower()

    log(state, f"[route_agent]: {routing_key}")

    # 3. 상태 업데이트
    return {**state, "input" : user_input, "status": routing_key}

def route_next(state: State) -> Literal["urgent_warning", "qna", "small_talk"]:
    decision = state.get("status", "").strip().lower() 
    
    if "urgent_warning" in decision:
        return "urgent_warning"
    elif "qna" in decision:
        return "qna"
    elif "small_talk" in decision:
        return "small_talk"
    else:
        return 'small_talk'