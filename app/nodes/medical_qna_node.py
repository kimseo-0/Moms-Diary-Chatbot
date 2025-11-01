# app/nodes/medical_qna_node.py
from __future__ import annotations
from typing import Dict, Any, List
from app.core.state import AgentState
from app.core.io_payload import InputEnvelope
from app.tools.rag_tools import search_medical_sources
from app.core.tooling import get_llm_with_tools

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.dependencies import get_openai
from app.core.config import config

SYSTEM = """너는 산모에게 안전하게 정보를 제공하는 의료 전문 어시스턴트야.
- 반드시 제공된 '근거'의 범위 안에서만 설명해.
- 단정적 진단/치료 지시는 피하고, 일반적 안전 수칙을 우선 제시해.
- 한국어로 간결하게 답변해.
"""

USER_TMPL = """[사용자 질문]
{question}

[검색 근거(발췌)]
{evidence}

요청:
- 위 '근거' 안에서만 핵심을 6~10문장으로 설명해.
"""

def _format_evidence(evs: List[Dict[str, Any]]) -> str:
    if not evs:
        return "근거 없음"
    lines = []
    for i, e in enumerate(evs, 1):
        src = e.get("source") or "unknown"
        page = e.get("page")
        p = f" p.{page}" if page is not None else ""
        snippet = (e.get("content") or "").strip()
        lines.append(f"[{i}] ({src}{p}) {snippet}")
    return "\n".join(lines[:6])

def medical_qna_node(state: AgentState) -> AgentState:
    """
    1) LangChain Retriever로 근거 검색
    2) LangChain Prompt/LLM 체인으로 전문가 답변 생성
    3) 결과를 state.metadata에 저장 -> 다음 노드에서 wrap_expert
    """
    env: InputEnvelope = state.input
    question = (env.payload.text or "").strip()

    # retreiver
    evidence: List[Dict[str, Any]] = search_medical_sources(question, top_k=5)
    evidence_str = _format_evidence(evidence)

    # chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM),
        ("user", USER_TMPL),
    ])
    llm = get_llm_with_tools(temperature=0)
    chain = prompt | llm | StrOutputParser()

    expert_text = chain.invoke({"question": question, "evidence": evidence_str}).strip()
    if "의료진 상담" not in expert_text:
        expert_text += "\n\n※ 본 정보는 일반적 안내이며, 개인 상태는 의료진 상담이 필요합니다."

    citations = [
        {k: v for k, v in e.items() if k in ("id", "source", "page", "score")}
        for e in evidence
    ]
    state.metadata["expert_raw"] = expert_text       # 다음 노드 wrap_expert에서 사용
    state.metadata["citations"] = citations          # UI 카드/요약 시 사용
    state.metadata["has_evidence"] = bool(evidence)

    return state
