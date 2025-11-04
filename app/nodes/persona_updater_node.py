"""
persona_updater_node

이 노드는 채팅(현재 발화)을 간단한 룰 또는 LLM으로 파싱해 프로필 후보를 추출하고
신뢰도가 충분하면 `ProfileRepository`를 통해 즉시(동기적으로) 아기/산모 프로필을 업데이트합니다.

주의: 병렬 처리는 LangGraph가 담당하도록 변경했습니다. 이 파일에서는 백그라운드
태스크를 만들지 않고 호출 시 즉시 업데이트를 실행합니다.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ValidationError
from app.core.state import AgentState
from app.core.logger import get_logger
from app.services.profile_repo import ProfileRepository, BabyProfile, MotherProfile
from app.core.dependencies import get_profile_repo

logger = get_logger(__name__)


def _extract_candidates(text: str) -> Dict[str, Any]:
    """Extract candidate profile fields for baby and mother and validate with Pydantic.

    Returns a dict like {"baby": {...}, "mother": {...}} with validated fields.
    If nothing extracted, returns {}.
    """
    if not text:
        return {}

    raw: Dict[str, Any] = {}

    # LLM-only extraction: invoke the parser and convert the parsed model into
    # baby/mother candidate dicts. If LLM extraction fails, return empty.
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

    # baby from parsed model
    try:
        baby_src = raw_candidate.get("baby") if isinstance(raw_candidate, dict) else None
        if baby_src and isinstance(baby_src, dict):
            baby_profile = BabyProfile(**baby_src)
    except ValidationError:
        logger.debug("persona_updater: baby candidate validation failed from LLM: %s", baby_src)

    # mother from parsed model
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
    # Use the shared ProfileRepository (configured with AppConfig.DB_PATH) so
    # the updater writes to the same DB as the rest of the application.
    repo: ProfileRepository = get_profile_repo()
    cands = _extract_candidates(text)
    if not cands:
        logger.debug("persona_updater: no candidates extracted for session=%s", session_id)
        return

    # Update baby profile if candidate present
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

    # Update mother profile if candidate present
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
    """노드로 호출되면 현재 발화를 기반으로 백그라운드에서 프로필 후보 추출/업데이트를 트리거한다."""
    session_id = state.session_id
    text = ""
    try:
        text = state.input.payload.text or ""
    except Exception:
        text = ""

    logger.info("persona_updater_node triggered for session=%s, text_len=%d", session_id, len(text))

    try:
        _process_and_update(session_id, text)
    except Exception:
        logger.exception("persona_updater: run failed for %s", session_id)

    return state


__all__ = ["persona_updater_node"]
