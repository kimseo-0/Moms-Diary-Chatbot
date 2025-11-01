# app/nodes/baby_smalltalk_node.py
from __future__ import annotations
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.tooling import get_llm_with_tools
from app.prompts.smalltalk_prompts import SMALLTALK_SYSTEM, SMALLTALK_USER, WRAP_SYSTEM, WRAP_USER
from app.core.dependencies import get_openai
from app.core.config import config
from app.core.state import AgentState
from app.core.io_payload import OutputEnvelope, InputEnvelope
from app.core.logger import get_logger

logger = get_logger(__name__)

def baby_smalltalk_node(state: AgentState, mode: str = "small_talk") -> AgentState:
    llm = get_llm_with_tools(temperature=0.0)
    logger.debug("baby_smalltalk_node 호출: mode=%s, session=%s", mode, state.input.session_id)

    if mode == "wrap_expert":
        expert_text = (state.metadata.get("expert_raw") or "").strip()
        prompt = ChatPromptTemplate.from_messages([
            ("system", WRAP_SYSTEM),
            ("user", WRAP_USER),
        ])
        chain = prompt | llm | StrOutputParser()
        baby_text = chain.invoke({"expert_text": expert_text}).strip()
        logger.info("baby_smalltalk_node.wrap_expert 응답 생성, session=%s, len=%d", state.input.session_id, len(baby_text))

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
    logger.info("baby_smalltalk_node.small_talk 응답 생성, session=%s, len=%d", state.input.session_id, len(baby_text))

    state.final = OutputEnvelope.ok_chat(
        text=baby_text,
        source="baby_smalltalk_node.small_talk",
    )
    return state
