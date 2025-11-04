from __future__ import annotations
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.prompts.plan_prompts import SYSTEM_PROMPT
from pydantic import BaseModel, Field
from app.core.state import AgentState
from app.core.config import config
from app.core.dependencies import get_openai
from app.core.tooling import get_llm
from app.core.logger import get_logger

logger = get_logger(__name__)

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

def plan_router_node(state: AgentState) -> AgentState:
    text = (state.input.payload.text or "").strip()
    logger.debug("plan_router_node 호출: session=%s, text_len=%d", state.input.session_id, len(text))

    parser = JsonOutputParser(pydantic_object=IntentOut)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "{user_input}")
    ]).partial(format_instructions=parser.get_format_instructions())

    # llm = get_llm_with_tools(temperature=0.0)
    # 전역 제어가 쉬운 중앙화된 get_llm을 사용해 LLM 인스턴스를 얻습니다.
    llm = get_llm(model_name=DEFAULT_LLM_MODEL, temperature=0.0)
    chain = prompt | llm | parser

    raw_out = chain.invoke({"user_input": text})
    out = IntentOut(**raw_out)

    intent = out.intent
    plan = INTENT_TO_PLAN.get(intent, DEFAULT_PLAN)
    state.plan = list(plan)
    state.metadata["route"] = intent
    logger.info("plan_router_node 판단 완료: intent=%s, plan_len=%d, session=%s", intent, len(state.plan), state.input.session_id)
    return state