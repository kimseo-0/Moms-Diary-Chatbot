from __future__ import annotations
from typing import Dict, Any
from datetime import date as _date
import time
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from app.core.tooling import get_llm_with_tools, get_llm
from app.prompts.diary_prompts import DETECT_SYSTEM, DIARY_SYSTEM_PROMPT
from app.core.dependencies import get_openai, get_chat_repo, get_diary_repo, get_profile_repo
from app.core.logger import get_logger
from app.core.config import config
from app.core.state import AgentState
from app.core.io_payload import OutputEnvelope, InputEnvelope
from app.services.diary_repo import DiaryEntry
from app.core.pydantic_utils import safe_model_dump

def diary_node(state: AgentState) -> AgentState:
    env: InputEnvelope = state.input
    text = (env.payload.text or "").strip()
    logger = get_logger(__name__)

    # LLM에게 대상 날짜 결정을 맡기고, 그 날짜의 메시지를 가져오기 위해
    # `get_chats_by_date` 툴을 사용합니다. 먼저 툴 사용 가능한 LLM에게
    # 날짜와 해당 날짜에 채팅이 존재하는지 판단하도록 요청합니다.
    chat_repo = get_chat_repo()
    from app.core.dependencies import get_profile_repo

    # 호출자가 metadata에 날짜를 제공한 경우에는 이를 바로 사용하고 LLM 판별을 건너뜁니다.
    meta_date = env.payload.metadata.date
    if meta_date:
        target_date = meta_date
    else:
        from pydantic import BaseModel

        class _DateDecisionModel(BaseModel):
            date: str

        detect_parser = PydanticOutputParser(pydantic_object=_DateDecisionModel)
        detect_prompt = ChatPromptTemplate.from_messages([
            ("system", DETECT_SYSTEM),
            ("user", "사용자 입력: {text}\n\n세션 ID: {session_id}")
        ]).partial(detector_format=detect_parser.get_format_instructions(), today_date=_date.today().isoformat())

        llm_tools = get_llm_with_tools(temperature=0.0)
        detect_chain = detect_prompt | llm_tools | detect_parser

        try:
            detect_out = detect_chain.invoke({"text": text, "session_id": env.session_id})
        except Exception as e:
            logger.warning("diary_node: date detection failed: %s", str(e))
            state.final = OutputEnvelope.ok_chat("일기 생성을 위한 날짜 판단에 실패했어요. 다시 시도해 주세요.", source="diary_node")
            return state

        target_date = detect_out.date

    # 결정된 날짜에 대해 실제 채팅 메시지를 조회합니다
    msgs = chat_repo.get_messages_by_date(env.session_id, target_date)
    if not msgs:
    # 선택한 날짜에 채팅이 없으면 일기를 생성하지 않습니다
        state.final = OutputEnvelope.ok_chat("해당 날짜에는 채팅기록이 없어요", source="diary_node")
        return state

    # 프롬프트에 넣을 형식으로 메시지를 정리합니다 (role: text)
    parts = [f"[{m.role}] {m.text}" for m in msgs]
    messages_text = "\n".join(parts)

    # UI 및 저장용으로 사용할 핵심 채팅 요약을 준비합니다
    used_chats = [{"role": m.role, "text": m.text, "created_at": m.created_at} for m in msgs[:5]]

    logger.debug("=== MESSAGES TEXT ===")
    logger.debug(messages_text)

    # 일기 생성에는 툴이 없는 일반 LLM을 사용합니다 — 날짜 판별에서만 툴을 사용했습니다.
    llm = get_llm(temperature=0.5)

    SYSTEM_PROMPT = DIARY_SYSTEM_PROMPT
    parser = PydanticOutputParser(pydantic_object=DiaryEntry)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "[사용자 요청] {text} \n\n [메시지 기록] {messages}\n [session id] {session_id}")
    ]).partial(diary_format=parser.get_format_instructions())

    # 히스토리/페르소나/어머니 프로필을 system prompt 슬롯으로 전달
    try:
        history_block = state.metadata.get("history_block") if state and state.metadata else None
        persona_section = ""
        history_section = ""
        if history_block:
            persona = history_block.get("persona")
            if persona:
                persona_section = "[페르소나]\n" + str(persona)
            recent = history_block.get("recent_chats") or []
            if recent:
                history_section = "[최근대화]\n" + "\n".join([f"[{r.get('role')}] {r.get('text')}" for r in recent[-20:]])
    except Exception:
        persona_section = ""
        history_section = ""

    mother_section = ""
    try:
        profile_repo = get_profile_repo()
        mother = profile_repo.get_mother(env.session_id)
        if mother:
            mother_section = "[어머니 프로필]\n" + (mother.model_dump() if hasattr(mother, "model_dump") else str(mother.__dict__))
    except Exception:
        mother_section = ""

    prompt = prompt.partial(persona_section=persona_section, history_section=history_section, mother_profile_section=mother_section)

    chain = prompt | llm | parser

    # 재시도 로직: 파서가 실패(예: LLM이 형식에 맞지 않는 출력을 반환)하면
    # 포기하기 전에 몇 번 재시도합니다. 실패 시 일기는 저장하지 않습니다.
    max_retries = 2
    diary = None
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 2):
        try:
            invoke_kwargs = {"messages": messages_text, "text": text, "session_id": env.session_id}
            # 히스토리/페르소나/어머니 프로필을 전달
            try:
                history_block = state.metadata.get("history_block") if state and state.metadata else None
                if history_block:
                    recent = history_block.get("recent_chats") or []
                    invoke_kwargs["history"] = "\n".join([f"[{r.get('role')}] {r.get('text')}" for r in recent[-20:]])
                    if history_block.get("persona"):
                        invoke_kwargs["persona"] = history_block.get("persona")
            except Exception:
                pass

            try:
                profile_repo = get_profile_repo()
                mother = profile_repo.get_mother(env.session_id)
                if mother:
                    invoke_kwargs["mother_profile"] = mother.model_dump() if hasattr(mother, "model_dump") else mother.__dict__
            except Exception:
                pass

            diary = chain.invoke(invoke_kwargs)
            break
        except Exception as e:
            # 실패를 로깅하고 재시도합니다 (시도 횟수 초과 시 제외)
            last_exc = e
            logger.warning("diary_node: parser/LLM invocation failed on attempt %d: %s", attempt, str(e))
            if attempt <= max_retries:
                # LLM을 과도하게 호출하지 않도록 짧은 백오프를 적용합니다
                time.sleep(1)
                continue
            # 최종 실패: 사용자에게 알리고 일기는 저장하지 않습니다
            state.final = OutputEnvelope.ok_chat(
                "일기 생성 중 파서 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
                source="diary_node",
            )
            return state

    diary_repo = get_diary_repo()
    # 요청/컨텍스트에서 권위있는 식별자(session_id, date)를 강제 설정합니다
    try:
        diary.session_id = env.session_id
    except Exception:
        pass
    try:
        diary.date = target_date
    except Exception:
        pass
    # 저장소가 영속화할 수 있도록 used_chats 리스트를 다이어리 모델에 첨부합니다
    try:
        diary.used_chats = used_chats
    except Exception:
        # diary가 plain dict이거나 속성이 없으면 무시합니다
        pass
    diary_repo.save_diary(diary)

    state.final = OutputEnvelope.ok_diary(
        text=diary.content,
        data={"diary": safe_model_dump(diary), "used_chats": used_chats},
        source="diary_node",
    )
    return state
