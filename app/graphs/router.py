# app/graphs/router.py
from __future__ import annotations
from typing import Literal

from app.core.state import AgentState
from app.core.dependencies import get_openai
from app.core.config import config

Route = Literal["urgent_triage", "medical_qna", "diary", "baby_smalltalk"]

# 휴리스틱 라우터
def route(state: AgentState) -> Route:
    text = (state.input.get("text") or "").strip()

    # 1) 위급 라우팅
    urgent_kw = ["119", "응급", "출혈", "호흡곤란", "실신", "경련", "의식없음"]
    if any(kw in text for kw in urgent_kw):
        state.plan = "urgent_triage"
        return "urgent_triage"

    # 2) 일기 라우팅
    diary_kw = ["일기", "다이어리", "오늘 기록", "기록해줘", "하루 정리"]
    if any(kw in text for kw in diary_kw):
        state.plan = "diary"
        return "diary"

    # 3) 메디컬 QnA 라우팅
    medical_kw = ["약", "복용", "증상", "통증", "부작용", "안전한가", "진통", "검사", "주수"]
    if any(kw in text for kw in medical_kw):
        state.plan = "medical_qna"
        return "medical_qna"

    # 4) 기본: 스몰톡
    state.plan = "baby_smalltalk"
    return "baby_smalltalk"

# LLM 기반 Router (Planner)
def llm_router(state: AgentState) -> AgentState:
    """
    LLM을 사용하여 사용자의 요청을 분석하고
    수행할 태스크 큐(plan)를 생성.
    """

    adapter = get_openai()
    llm = adapter.get_llm(model=config.DEFAULT_LLM_MODEL, temperature=0)

    user_text = state.input.get("text") or ""

    system_prompt = f"""
        너는 태아 챗봇의 플래너야. 엄마의 입력을 보고 어떤 노드들이 필요할지 계획을 세워.
        [허용 노드] {sorted(Route)}
        - urgent_triage: 응급상황이 의심되는 경우 (119, 출혈, 호흡곤란 등)
        - medical_qna: 약물, 통증, 검사, 증상 등 의학적 질문
        - diary: 일기, 기록, 하루 요약, 감정 정리
        - baby_smalltalk: 단순 대화나 감정 표현

        [출력 형식]
        JSON으로 답하라. 필드:
        {{
        first_node: 노드 이름 (위 중 하나),
        task_queue: 노드 리스트 ex) ["medical_qna", "baby_smalltalk", ...]
        }}
    """

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"입력: {user_text}"}
    ]

    response = llm.invoke(prompt)
    content = response.content.strip()

    import json
    try:
        parsed = json.loads(content)
        first_node = parsed.get("first_node", "baby_smalltalk")
        plan = parsed.get("task_queue", [first_node])
    except Exception:
        first_node = "baby_smalltalk"
        plan = [first_node]

    # 상태 업데이트
    state.plan = plan
    state.metadata["route"] = first_node
    return state