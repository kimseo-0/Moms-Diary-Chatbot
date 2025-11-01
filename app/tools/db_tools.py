# app/tools/db_tools.py
from langchain.agents import tool
from app.core.dependencies import get_chat_repo, get_diary_repo, get_profile_repo
from app.services.chat_repo import ChatLog
from app.services.diary_repo import DiaryEntry
from app.services.profile_repo import BabyProfile, MotherProfile

chat_repo = get_chat_repo()
diary_repo = get_diary_repo()
profile_repo = get_profile_repo()


@tool("save_chat", return_direct=False)
def save_chat_tool(session_id: str, role: str, text: str, meta_json: str | None = None):
    """채팅 로그를 DB에 저장합니다."""
    chat_repo.save_message(ChatLog(session_id=session_id, role=role, text=text, meta_json=meta_json))
    return {"ok": True}


@tool("get_recent_chats", return_direct=False)
def get_recent_chats_tool(session_id: str, limit: int = 10):
    """최근 대화 N개를 조회합니다."""
    messages = chat_repo.get_recent_messages(session_id, limit)
    return [m.model_dump() for m in messages]


@tool("get_chats_by_date", return_direct=False)
def get_chats_by_date_tool(session_id: str, target_date: str):
    """특정 날짜(YYYY-MM-DD)의 메시지 조회를 도와주는 툴입니다."""
    messages = chat_repo.get_messages_by_date(session_id, target_date)
    return [m.model_dump() for m in messages]


@tool("save_diary", return_direct=False)
def save_diary_tool(session_id: str, content: str, date: str):
    """일기를 저장합니다."""
    diary_repo.save_diary(DiaryEntry(session_id=session_id, date=date, content=content))
    return {"ok": True}


@tool("get_diary_list", return_direct=False)
def get_diary_list_tool(session_id: str):
    """저장된 일기 목록을 반환합니다."""
    diaries = diary_repo.list_diaries(session_id)
    return [d.model_dump() for d in diaries]


@tool("get_profile", return_direct=False)
def get_profile_tool(session_id: str):
    """아기/산모 프로필을 조회합니다."""
    baby = profile_repo.get_baby(session_id)
    mother = profile_repo.get_mother(session_id)
    return {"baby": baby.model_dump() if baby else None, "mother": mother.model_dump() if mother else None}


@tool("update_baby_profile", return_direct=False)
def update_baby_profile_tool(session_id: str, name: str | None = None, week: int | None = None):
    """아기 프로필을 업데이트합니다."""
    profile_repo.upsert_baby(BabyProfile(session_id=session_id, name=name, week=week))
    return {"ok": True}

@tool("update_mother_profile", return_direct=False)
def update_mother_profile_tool(session_id: str, name: str | None = None, week: int | None = None):
    """산모 프로필을 업데이트합니다."""
    profile_repo.upsert_mother(MotherProfile(session_id=session_id, name=name))
    return {"ok": True}