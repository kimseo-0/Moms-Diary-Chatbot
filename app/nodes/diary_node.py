# app/nodes/diary_node.py
from __future__ import annotations
from typing import Dict, Any
from datetime import date as _date
import time
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from app.core.tooling import get_llm_with_tools, get_llm
from app.core.dependencies import get_openai, get_chat_repo, get_diary_repo
from app.core.config import config
from app.core.state import AgentState
from app.core.io_payload import OutputEnvelope, InputEnvelope
from app.services.diary_repo import DiaryEntry

def diary_node(state: AgentState) -> AgentState:
    env: InputEnvelope = state.input
    text = (env.payload.text or "").strip()
    # We'll let the LLM decide the target date and use the tool
    # `get_chats_by_date` to fetch messages for that date. First, ask the
    # LLM (with tools enabled) to determine the date and whether chats exist.
    chat_repo = get_chat_repo()

    # If the caller provided a date in metadata, use it directly and skip LLM detection.
    meta_date = env.payload.metadata.date
    if meta_date:
        target_date = meta_date
    else:
        from pydantic import BaseModel
        class _DateDecisionModel(BaseModel):
            date: str

        detect_system = (
            """
            다음 사용자의 일기 작성 요청에 대한 입력을 보고
            오늘 날짜를 기준으로 이 요청에 해당하는 '날짜'를 판단해야해
            
            [규칙]
            - 중요: 반드시 아래 파이단틱 모델 형식을 정확히 지켜서 JSON으로 응답해. 다른 말은 하지 말고 JSON만 반환해
            - 가능한 경우에는 정확한 날짜(예: 2025-10-31)를 반환해
            - 날짜를 추론할 수 없으면 오늘 날짜를 사용

            [오늘 날짜]
            {today_date}

            [출력 형식] 
            {detector_format}
            """
        )

        detect_parser = PydanticOutputParser(pydantic_object=_DateDecisionModel)
        detect_prompt = ChatPromptTemplate.from_messages([
            ("system", detect_system),
            ("user", "사용자 입력: {text}\n\n세션 ID: {session_id}")
        ]).partial(detector_format=detect_parser.get_format_instructions(), today_date=_date.today().isoformat())

        llm_tools = get_llm_with_tools(temperature=0.0)
        detect_chain = detect_prompt | llm_tools | detect_parser

        # Run detection with retries
        try:
            detect_out = detect_chain.invoke({"text": text, "session_id": env.session_id})
        except Exception as e:
            logging.warning("diary_node: date detection failed: %s", str(e))
            state.final = OutputEnvelope.ok_chat("일기 생성을 위한 날짜 판단에 실패했어요. 다시 시도해 주세요.", source="diary_node")
            return state

        target_date = detect_out.date

    # Fetch actual chats for the determined date
    msgs = chat_repo.get_messages_by_date(env.session_id, target_date)
    if not msgs:
        # If no chats for the chosen date, do NOT create diary
        state.final = OutputEnvelope.ok_chat("해당 날짜에는 채팅기록이 없어요", source="diary_node")
        return state

    # Format messages for the prompt (role: text)
    parts = [f"[{m.role}] {m.text}" for m in msgs]
    messages_text = "\n".join(parts)

    # Prepare a small summary of core chats used for UI and storage
    used_chats = [{"role": m.role, "text": m.text, "created_at": m.created_at} for m in msgs[:5]]

    print()
    print("=== MESSAGES TEXT ===")
    print(messages_text)

    # Use a plain LLM (no tools) for diary generation — detection used tools above.
    llm = get_llm(temperature=0.5)
    
    SYSTEM_PROMPT = """
        너는 태아(아기)의 시점에서 엄마와의 하루를 기록하는 일기 작성 어시스턴트야.
        사용자가 입력한 메세지 기록을 참고해서 일기를 작성해

        [중요: 반드시 아래 파이단틱 모델 형식을 정확히 지켜서 JSON으로 응답해. 다른 말은 하지 말고 JSON만 반환해]
        {diary_format}

        [일기 작성 지침]
        - 말투는 따뜻하고 감정이 느껴지게
        - '오늘 엄마가 ... 해줬어'처럼 구체적 묘사
        - 제목 작성하기
        - 3~6문장 이내로, 일기 형식
        - 날짜나 요일 언급 가능
        - 금지: 공포/의학/과격 단어
    """
    parser = PydanticOutputParser(pydantic_object=DiaryEntry)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "[사용자 요청] {text} \n\n [메시지 기록] {messages}\n [session id] {session_id}")
    ]).partial(diary_format=parser.get_format_instructions())

    chain = prompt | llm | parser

    # Retry logic: if the parser fails (e.g., LLM returns non-matching JSON),
    # retry a couple of times before giving up. Do NOT save the diary on failure.
    max_retries = 2
    diary = None
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            diary = chain.invoke({
                "messages": messages_text,
                "text": text,
                "session_id": env.session_id
            })
            break
        except Exception as e:
            # Log and retry (unless we've exhausted attempts)
            last_exc = e
            logging.warning("diary_node: parser/LLM invocation failed on attempt %d: %s", attempt, str(e))
            if attempt <= max_retries:
                # small backoff to avoid hammering the LLM
                time.sleep(1)
                continue
            # final failure: inform the user and do not save a diary
            state.final = OutputEnvelope.ok_chat(
                "일기 생성 중 파서 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
                source="diary_node",
            )
            return state

    diary_repo = get_diary_repo()
    # Enforce authoritative identifiers from the request/context
    try:
        diary.session_id = env.session_id
    except Exception:
        pass
    try:
        diary.date = target_date
    except Exception:
        pass
    # Attach the used_chats list to the diary model so the repository can persist it
    try:
        diary.used_chats = used_chats
    except Exception:
        # If diary is a plain dict or lacks attribute, ignore
        pass
    diary_repo.save_diary(diary)

    state.final = OutputEnvelope.ok_diary(
        text=diary.content,
        data={"diary": diary.model_dump(), "used_chats": used_chats},
        source="diary_node",
    )
    return state
