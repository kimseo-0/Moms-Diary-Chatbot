from __future__ import annotations
import asyncio
import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ValidationError
from app.core.state import AgentState
from app.core.logger import get_logger
from app.services.profile_repo import ProfileRepository, BabyProfile, MotherProfile
from app.core.dependencies import get_profile_repo

logger = get_logger(__name__)


def _extract_candidates(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    raw: Dict[str, Any] = {}

    try:
        system_prompt = (
            """
            당신은 문장 분석 전문가입니다. 문장이 내포하고 있는 의미들을 정확하게 분석할 수 있습니다.
            사용자의 입력을 분석하여 아기 및 산모 프로필 정보를 추출해야합니다.

            반드시 주어진 형식의 JSON만 반환해야합니다.
            [출력 형식]
            {data_format}
            """
        )

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import PydanticOutputParser
        from app.core.tooling import get_llm

        class CandidateProfile(BaseModel):
            baby: Optional[BabyProfile] = None
            mother: Optional[MotherProfile] = None

        parser = PydanticOutputParser(pydantic_object=CandidateProfile)

        llm = get_llm(temperature=0.0)
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "[사용자 입력] {text}"),
        ]).partial(data_format=parser.get_format_instructions())

        chain = chat_prompt | llm | parser

        parsed_model = chain.invoke({"text": text})
        # normalize to plain dict
        if hasattr(parsed_model, "model_dump"):
            raw_candidate = parsed_model.model_dump()
        elif hasattr(parsed_model, "dict"):
            raw_candidate = parsed_model.dict()
        else:
            raw_candidate = dict(parsed_model)

    except Exception:
        logger.debug("persona_updater: LLM extraction failed, returning no candidates")
        return {}

    candidates: Dict[str, Any] = {}

    try:
        baby_src = raw_candidate.get("baby") if isinstance(raw_candidate, dict) else None
        if baby_src and isinstance(baby_src, dict):
            baby_profile = BabyProfile(**baby_src)
    except ValidationError:
        logger.debug("persona_updater: baby candidate validation failed from LLM: %s", baby_src)

    try:
        mother_src = raw_candidate.get("mother") if isinstance(raw_candidate, dict) else None
        if mother_src and isinstance(mother_src, dict):
            mother_profile = MotherProfile(**mother_src)
    except ValidationError:
        logger.debug("persona_updater: mother candidate validation failed from LLM: %s", mother_src)

    candidates = {
        "baby": baby_profile,
        "mother": mother_profile,
    }
    print("=== Profile Candidates ===")
    print(candidates)
    return candidates


def _process_and_update(session_id: str, text: str) -> None:
    repo: ProfileRepository = get_profile_repo()
    cands = _extract_candidates(text)
    if not cands:
        logger.debug("persona_updater: no candidates extracted for session=%s", session_id)
        return

    baby_c = cands.get("baby")
    if baby_c:
        baby = repo.get_baby(session_id) or BabyProfile(session_id=session_id)
        updated = False
        if baby_c.get("name") or not baby.name:
            baby.name = baby_c.get("name")
            updated = True
        if baby_c.get("week") or not baby.week:
            baby.week = int(baby_c.get("week"))
            updated = True
        if baby_c.get("gender") or (not baby.gender or baby.gender == "U"):
            baby.gender = baby_c.get("gender")
            updated = True

        if updated:
            try:
                repo.upsert_baby(baby)
                logger.info("persona_updater: baby profile updated for session=%s", session_id)
            except Exception:
                logger.exception("persona_updater: failed to update baby profile for %s", session_id)

    mother_c = cands.get("mother")
    if mother_c:
        try:
            mother = repo.get_mother(session_id) or MotherProfile(session_id=session_id)
        except Exception:
            # ProfileRepository may raise; fall back to creating object
            mother = MotherProfile(session_id=session_id)

        m_updated = False
        if mother_c.get("name") or not mother.name:
            mother.name = mother_c.get("name")
            m_updated = True
        if mother_c.get("age") is not None or not mother.age:
            try:
                mother.age = int(mother_c.get("age"))
                m_updated = True
            except Exception:
                pass

        if m_updated:
            try:
                repo.upsert_mother(mother)
                logger.info("persona_updater: mother profile updated for session=%s", session_id)
            except Exception:
                logger.exception("persona_updater: failed to update mother profile for %s", session_id)


def persona_updater_node(state: AgentState) -> AgentState:
    session_id = state.session_id
    text = ""
    try:
        text = state.input.payload.text or ""
    except Exception:
        text = ""

    logger.info("persona_updater_node triggered for session=%s, text_len=%d", session_id, len(text))

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        asyncio.create_task(_process_and_update(session_id, text))
    else:
        logger.info("persona_agent_node: event loop not running, running task in background via asyncio.run()")
        try:
            asyncio.run(_process_and_update(session_id, text))
        except Exception:
            logger.exception("persona_updater: run failed for %s", session_id)

    return state

__all__ = ["persona_updater_node"]
