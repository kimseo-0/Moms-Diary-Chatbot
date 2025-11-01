# app/nodes/baby_smalltalk_node.py
from __future__ import annotations
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.tooling import get_llm_with_tools
from app.core.dependencies import get_openai
from app.core.config import config
from app.core.state import AgentState
from app.core.io_payload import OutputEnvelope, InputEnvelope

# Small talk (일상 대화)
SMALLTALK_SYSTEM = (
    "너는 태아(아기)의 1인칭 시점으로 대화하는 AI야.\n"
    "- 항상 엄마에게 말하듯이 '엄마~'라고 시작하거나 부드럽게 말해.\n"
    "- 1~3문장, 240자 이내.\n"
    "- 내용은 따뜻하고 공감있게, 질문에는 짧게 답변.\n"
    "- 공포, 불안, 부정적 표현 금지."
)
SMALLTALK_USER = "엄마가 한 말: {user_input}"


# wrap_expert 모드 (전문가 답변 요약)
WRAP_SYSTEM = (
    "너는 태아(아기)의 말투로 전문가의 긴 설명을 요약해서 엄마에게 전하는 역할을 해.\n"
    "- 전문가 답변을 왜곡하지 말고 핵심만 부드럽게 말해.\n"
    "- 1~3문장.\n"
    "- 공포나 부정 표현 금지."
)
WRAP_USER = "전문가의 답변:\n{expert_text}\n\n이 내용을 엄마에게 아기 말투로 짧게 전해줘."

def baby_smalltalk_node(state: AgentState, mode: str = "small_talk") -> AgentState:
    llm = get_llm_with_tools(temperature=0.0)

    if mode == "wrap_expert":
        expert_text = (state.metadata.get("expert_raw") or "").strip()
        prompt = ChatPromptTemplate.from_messages([
            ("system", WRAP_SYSTEM),
            ("user", WRAP_USER),
        ])
        chain = prompt | llm | StrOutputParser()
        baby_text = chain.invoke({"expert_text": expert_text}).strip()

        state.final = OutputEnvelope.ok_expert(
            text=baby_text,
            data={
                "citations": state.metadata.get("citations", []),
                "raw": expert_text,
            },
            source="baby_smalltalk_node.wrap_expert",
        )
        return state

    # ─ 기본 small_talk 모드 ─
    env: InputEnvelope = state.input
    text = (env.payload.text or "").strip()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SMALLTALK_SYSTEM),
        ("user", SMALLTALK_USER),
    ])

    chain = prompt | llm | StrOutputParser()
    baby_text = chain.invoke({"user_input": text}).strip()

    state.final = OutputEnvelope.ok_chat(
        text=baby_text,
        source="baby_smalltalk_node.small_talk",
    )
    return state
