# app/nodes/plan_router_node.py
from __future__ import annotations
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from app.core.state import AgentState
from app.core.config import config
from app.core.dependencies import get_openai

DEFAULT_LLM_MODEL = getattr(config, "DEFAULT_LLM_MODEL", "gpt-4o-mini")

INTENT_TO_PLAN: Dict[str, list[dict]] = {
    "urgent_triage": [{"kind":"node","name":"urgent_triage_node"},
                      {"kind":"render","name":"render_chat_output_tool","args":{"meta_type":"safety_alert"}}],
    "medical_qna":   [{"kind":"node","name":"medical_qna_node"},
                      {"kind":"node","name":"baby_smalltalk_node","args":{"mode":"wrap_expert"}},
                      {"kind":"render","name":"render_chat_output_tool","args":{"meta_type":"expert_answer"}}],
    "diary":         [{"kind":"node","name":"diary_node"},
                      {"kind":"render","name":"render_chat_output_tool","args":{"meta_type":"diary_entry"}}],
    "baby_smalltalk":[{"kind":"node","name":"baby_smalltalk_node","args":{"mode":"small_talk"}},
                      {"kind":"render","name":"render_chat_output_tool","args":{"meta_type":"chat"}}],
}
DEFAULT_PLAN = INTENT_TO_PLAN["baby_smalltalk"]

class IntentOut(BaseModel):
    intent: str = Field(pattern="^(urgent_triage|medical_qna|diary|baby_smalltalk)$")

SYSTEM_PROMPT = """
너는 20년차 산부인과 전문의로서 산모의 문장을 보고 어떤 대답이 좋을지 정확히 분류할 수 있어
목표는 산모의 한 문장을 읽고 의도를 아래 네 가지 중 하나로 "정확히 하나"만 분류하는 것이야

[intent 클래스]
- urgent_triage: 응급이 의심되는 경우. 예) 호흡곤란, 의식저하/실신, 질출혈/양수의심(물 같은 액체 쏟음), 지속적/격심한 복통·경련, 고열(38.5℃↑)과 심한 증상 동반, 태동 급감/소실, 심한 두통·시야장애, 심한 어지럼·호흡곤란·가슴통증, 사고 직후 통증 등
- medical_qna: 약물/용량/성분/복용 가능 여부, 검사/수치/초음파/주차별 의학적 질문, 증상 상담(응급 징후 미포함), 생활수칙 의료적 판단이 필요한 질문
- diary: 일기/기록/회고/메모/한 줄 등 하루 요약·기록 지향 문장(주의 사항: 오늘, 어제 등 날짜가 나왔다고 무조건 일기 작성 아님)
- baby_smalltalk: 인사/잡담/감정 표현/칭찬/요청 등 일반 대화(의학 판단·기록 지향 아님)

[우선순위 규칙]
1) urgent_triage > 2) medical_qna > 3) diary > 4) baby_smalltalk

[출력 형식]
아래 JSON만 단독으로 출력해. 추가 텍스트 금지.
{format_instructions}
"""

def plan_router_node(state: AgentState) -> AgentState:
    text = (state.input.payload.text or "").strip()

    parser = JsonOutputParser(pydantic_object=IntentOut)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "{user_input}")
    ]).partial(format_instructions=parser.get_format_instructions())

    # llm = get_llm_with_tools(temperature=0.0)
    oa = get_openai()
    llm = oa.get_llm(
        model=DEFAULT_LLM_MODEL,
        temperature=0.0
    )
    chain = prompt | llm | parser

    raw_out = chain.invoke({"user_input": text})
    out = IntentOut(**raw_out)

    intent = out.intent

    plan = INTENT_TO_PLAN.get(intent, DEFAULT_PLAN)
    state.plan = list(plan)
    state.metadata["route"] = intent
    return state