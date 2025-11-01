# app/tools/db_tools.py
from langchain.agents import tool
from app.core.dependencies import get_chat_repo, get_diary_repo, get_profile_repo
from app.services.chat_repo import ChatLog
from app.services.diary_repo import DiaryEntry
from app.services.profile_repo import BabyProfile, MotherProfile
from app.core.logger import get_logger
from app.core.pydantic_utils import safe_model_dump

logger = get_logger(__name__)

# Note: these getters are cached; calling them here is acceptable but kept minimal
chat_repo = get_chat_repo()
diary_repo = get_diary_repo()
profile_repo = get_profile_repo()


@tool("save_chat", return_direct=False)
def save_chat_tool(session_id: str, role: str, text: str, meta_json: str | None = None):
    """채팅 로그를 DB에 저장합니다."""
    logger.info("툴(save_chat) 호출: session=%s, role=%s, text_len=%d", session_id, role, len(text or ""))
    chat_repo.save_message(ChatLog(session_id=session_id, role=role, text=text, meta_json=meta_json))
    logger.debug("툴(save_chat) 완료: session=%s", session_id)
    return {"ok": True}


@tool("get_recent_chats", return_direct=False)
def get_recent_chats_tool(session_id: str, limit: int = 10):
    """최근 대화 N개를 조회합니다."""
    logger.info("툴(get_recent_chats) 호출: session=%s, limit=%d", session_id, limit)
    messages = chat_repo.get_recent_messages(session_id, limit)
    logger.debug("툴(get_recent_chats) 결과 수: %d", len(messages))
    return [safe_model_dump(m) for m in messages]


@tool("get_chats_by_date", return_direct=False)
def get_chats_by_date_tool(session_id: str, target_date: str):
    """특정 날짜(YYYY-MM-DD)의 메시지 조회를 도와주는 툴입니다."""
    logger.info("툴(get_chats_by_date) 호출: session=%s, date=%s", session_id, target_date)
    messages = chat_repo.get_messages_by_date(session_id, target_date)
    logger.debug("툴(get_chats_by_date) 결과 수: %d", len(messages))
    return [safe_model_dump(m) for m in messages]


@tool("save_diary", return_direct=False)
def save_diary_tool(session_id: str, content: str, date: str):
    """일기를 저장합니다."""
    logger.info("툴(save_diary) 호출: session=%s, date=%s, content_len=%d", session_id, date, len(content or ""))
    diary_repo.save_diary(DiaryEntry(session_id=session_id, date=date, content=content))
    logger.debug("툴(save_diary) 완료: session=%s, date=%s", session_id, date)
    return {"ok": True}


@tool("get_diary_list", return_direct=False)
def get_diary_list_tool(session_id: str):
    """저장된 일기 목록을 반환합니다."""
    logger.info("툴(get_diary_list) 호출: session=%s", session_id)
    diaries = diary_repo.list_diaries(session_id)
    logger.debug("툴(get_diary_list) 결과 수: %d", len(diaries))
    return [safe_model_dump(d) for d in diaries]


@tool("get_profile", return_direct=False)
def get_profile_tool(session_id: str):
    """아기/산모 프로필을 조회합니다."""
    logger.info("툴(get_profile) 호출: session=%s", session_id)
    baby = profile_repo.get_baby(session_id)
    mother = profile_repo.get_mother(session_id)
    logger.debug("툴(get_profile) 완료: session=%s, baby=%s, mother=%s", session_id, bool(baby), bool(mother))
    return {"baby": safe_model_dump(baby) if baby else None, "mother": safe_model_dump(mother) if mother else None}


@tool("update_baby_profile", return_direct=False)
def update_baby_profile_tool(session_id: str, name: str | None = None, week: int | None = None):
    """아기 프로필을 업데이트합니다."""
    logger.info("툴(update_baby_profile) 호출: session=%s, name=%s, week=%s", session_id, name, week)
    profile_repo.upsert_baby(BabyProfile(session_id=session_id, name=name, week=week))
    logger.debug("툴(update_baby_profile) 완료: session=%s", session_id)
    return {"ok": True}

@tool("update_mother_profile", return_direct=False)
def update_mother_profile_tool(session_id: str, name: str | None = None, week: int | None = None):
    """산모 프로필을 업데이트합니다."""
    logger.info("툴(update_mother_profile) 호출: session=%s, name=%s", session_id, name)
    profile_repo.upsert_mother(MotherProfile(session_id=session_id, name=name))
    logger.debug("툴(update_mother_profile) 완료: session=%s", session_id)
    return {"ok": True}