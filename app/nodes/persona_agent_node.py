from __future__ import annotations
import asyncio
import json
from typing import Any
from pydantic import BaseModel, Field
from app.core.state import AgentState
from app.core.logger import get_logger
from app.services import persona_repo
from app.core.tooling import get_llm

logger = get_logger(__name__)


async def _build_and_save_persona(session_id: str, history_block: dict[str, Any]) -> None:
    """백그라운드에서 실행되는 실제 작업 함수.

    LLM을 사용해 페르소나 JSON을 생성하고 저장합니다. LLM 실패 시 기존 간단한 페르소나를 저장합니다.
    """
    try:
        # LLM에 전달할 내용 준비
        recent = history_block.get("recent_chats", []) or []
        weekly = history_block.get("weekly_summaries", []) or []
        recent_text = "\n".join([f"[{r.get('role')}] {r.get('text')}" for r in recent[-20:]])
        weekly_text = "\n".join([f"- {ws.get('week_start')}: {ws.get('summary')}" for ws in weekly])

        prompt = """
        다음은 사용자 세션의 최근 대화와 주간 요약입니다. 
        이것을 바탕으로 '아기(태아)를 대표하는 간단한 페르소나'를 JSON으로 생성해 주세요.

        요구사항:
        - 출력은 반드시 JSON 형식만 반환하세요.
        - 주요 필드:
        - summary: 한 문단으로 된 요약 문자열
        - traits: 아이의 성격/특성 리스트, 요약을 바탕으로 키워드를 최소 2개 이상 (예: 활발함, 수면불규칙 등)
        - recent: 최근 대화(텍스트 리스트) - 선택적
        - tags: (선택) traits에서 파생된 짧은 키워드 리스트

        RECENT:
        {recent_text}

        WEEKLY:
        {weekly_text}

        출력 예시:
        {data_format}
        """

        llm = get_llm(temperature=0.0)
        # Use a Pydantic parser to enforce schema from the LLM output
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import PydanticOutputParser

            class PersonaModel(BaseModel):
                summary: str = Field(description="한 문단으로 된 아이 페르소나 요약 문자")
                traits: list[str] = Field(description="아이의 성격/특성 리스트", min_length=2)
                recent: list[Any] = Field(description="최근 대화 내용 리스트")
                weekly: list[Any] = Field(description="주간 요약 리스트")
                tags: list[str] | None = Field(description="페르소나 특성에서 파생된 짧은 키워드 리스트", default=None)

            parser = PydanticOutputParser(pydantic_object=PersonaModel)

            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "아래 지시에 따라 JSON만 반환해주세요."),
                ("user", prompt),
            ]).partial(data_format=parser.get_format_instructions(), recent_text=recent_text, weekly_text=weekly_text)

            chain = chat_prompt | llm | parser
            parsed_model = chain.invoke({})

            # normalize to plain dict
            if hasattr(parsed_model, "model_dump"):
                persona_obj = parsed_model.model_dump()
            elif hasattr(parsed_model, "dict"):
                persona_obj = parsed_model.dict()
            else:
                persona_obj = dict(parsed_model)
        except Exception:
            # LLM/parser 실패 시 폴백: 단순 조합
            persona_obj = PersonaModel(
                summary="; ".join([ws.get("summary", "") for ws in weekly]) or "",
                traits=[],
                recent=recent,
                weekly=weekly,
                tags=None,
            ).model_dump()

        # Ensure persona has traits and derived tags
        try:
            traits = persona_obj.get("traits") if isinstance(persona_obj, dict) else None
            if not traits:
                # fallback to empty list
                traits = []
                persona_obj["traits"] = traits

            # derive simple normalized tags from traits (lowercase, short)
            try:
                tags = []
                for t in traits:
                    if not isinstance(t, str):
                        continue
                    tt = t.strip().lower()
                    if tt:
                        # keep only short tokens (max 3 words)
                        parts = tt.split()
                        tags.append(" ".join(parts[:3]))
                # deduplicate while preserving order
                seen = set()
                tags_clean = []
                for t in tags:
                    if t not in seen:
                        seen.add(t)
                        tags_clean.append(t)
                persona_obj["tags"] = tags_clean
            except Exception:
                persona_obj.setdefault("tags", [])

            persona_repo.insert_child_persona(session_id=session_id, persona_json=json.dumps(persona_obj, ensure_ascii=False))
            logger.info("persona_agent: persona saved for session=%s", session_id)
        except Exception:
            logger.exception("persona_agent: failed to persist persona for %s", session_id)
    except Exception as e:
        logger.exception("persona_agent: error while building/saving persona for %s: %s", session_id, e)


def persona_agent_node(state: AgentState) -> AgentState:
    """노드로 호출되면 history_block을 읽고 백그라운드 태스크로 persona 생성을 트리거합니다."""
    session_id = state.session_id
    history_block = state.metadata.get("history_block")
    if not history_block:
        logger.warning("persona_agent_node: no history_block found for session=%s", session_id)
        return state

    # 백그라운드로 태스크 생성(논-블로킹)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # 노드가 동기 환경에서 호출될 경우 새 루프에서 실행
        loop = None

    if loop and loop.is_running():
        asyncio.create_task(_build_and_save_persona(session_id, history_block))
    else:
        # 동기 환경: 바로 백그라운드 스레드에서 실행하지 않고, 미래 호출을 위해 스케줄러에 등록하도록 로깅
        logger.info("persona_agent_node: event loop not running, running task in background via asyncio.run()")
        try:
            asyncio.run(_build_and_save_persona(session_id, history_block))
        except Exception:
            logger.exception("persona_agent_node: failed to run background persona task synchronously for %s", session_id)

    return state


__all__ = ["persona_agent_node"]
