# app/api/http.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.core.io_payload import InputEnvelope, OutputEnvelope, InputPayload, InputMetadata
from app.graphs.main_graph import compile_app_graph
from app.core.state import AgentState
from app.core.dependencies import get_diary_repo, get_chat_repo, get_profile_repo
from app.services.diary_repo import DiaryEntry
from app.services.chat_repo import ChatLog
from app.services.profile_repo import BabyProfile, MotherProfile
import json
from pydantic import BaseModel

router = APIRouter()

# 컴파일된 그래프 싱글톤
_graph = compile_app_graph()


@router.post("/chat", response_model=OutputEnvelope)
def chat(envelope: InputEnvelope) -> OutputEnvelope:
    # Ensure profile exists for this session (defensive)
    try:
        profile_repo = get_profile_repo()
        if profile_repo.get_baby(envelope.session_id) is None:
            profile_repo.upsert_baby(BabyProfile(session_id=envelope.session_id))
        if profile_repo.get_mother(envelope.session_id) is None:
            profile_repo.upsert_mother(MotherProfile(session_id=envelope.session_id))
    except Exception:
        pass

    try:
        chat_repo = get_chat_repo()
        try:
            user_meta = envelope.payload.metadata.model_dump()
        except Exception:
            try:
                user_meta = envelope.payload.metadata.model_dump()  # pydantic v2 fallback
            except Exception:
                # Fallback to simple dict conversion
                user_meta = envelope.payload.metadata.__dict__ if hasattr(envelope.payload.metadata, "__dict__") else {}

        chat_repo.save_message(
            ChatLog(
                session_id=envelope.session_id,
                role="user",
                text=envelope.payload.text,
                meta_json=json.dumps(user_meta, ensure_ascii=False),
                created_at=None,
            )
        )
    except Exception as e:
        print(f"⚠️ 사용자 메시지 저장 실패: {e}")
        import traceback
        traceback.print_exc()

    state_in = AgentState(session_id=envelope.session_id, input=envelope)
    state_out = AgentState(**_graph.invoke(state_in))

    try:
        chat_repo = get_chat_repo()
        final = state_out.final
        if final and getattr(final, "result", None):
            res = final.result
            # Serialize full result (text, data, meta) so UI can render by type
            try:
                res_meta = res.meta.model_dump()
            except Exception:
                res_meta = res.meta.__dict__ if hasattr(res.meta, "__dict__") else {}

            # Try to get data dict if present
            try:
                res_data = res.data if hasattr(res, "data") else {}
            except Exception:
                res_data = {}

            result_obj = {
                "text": getattr(res, "text", ""),
                "data": res_data,
                "meta": res_meta,
            }

            chat_repo.save_message(
                ChatLog(
                    session_id=envelope.session_id,
                    role="assistant",
                    text=result_obj.get("text", ""),
                    meta_json=json.dumps(result_obj, ensure_ascii=False),
                    created_at=None,
                )
            )
    except Exception as e:
        print(f"⚠️ 어시스턴트 메시지 저장 실패: {e}")
        import traceback
        traceback.print_exc()

    return state_out.final or OutputEnvelope.err("INTERNAL_ERROR", "응답 생성 실패", retryable=False)


# ----- Diary endpoints -----
class DiarySaveRequest(BaseModel):
    session_id: str
    date: str
    content: str


@router.post("/diary", response_model=dict)
def save_diary(payload: DiarySaveRequest):
    repo = get_diary_repo()
    repo.save_diary(DiaryEntry(session_id=payload.session_id, date=payload.date, content=payload.content))
    return {"ok": True, "date": payload.date}


@router.get("/diary/{session_id}/{target_date}", response_model=dict)
def get_diary(session_id: str, target_date: str):
    repo = get_diary_repo()
    d = repo.get_diary_by_date(session_id, target_date)
    print(d)
    if d:  # diary exists in DB - return it immediately
        return {"ok": True, "diary": d.model_dump()}
    
    # Diary doesn't exist - trigger generation via diary node
    metadata = InputMetadata(type="diary", date=target_date, week=None, language="ko")
    payload = InputPayload(text=f"일기 작성해줘", metadata=metadata)
    envelope = InputEnvelope(session_id=session_id, payload=payload)
    
    # Route through diary node
    state_in = AgentState(session_id=session_id, input=envelope)
    state_out = AgentState(**_graph.invoke(state_in))

    print(state_out)
    
    # Re-fetch diary after generation
    d = repo.get_diary_by_date(session_id, target_date)
    return {"ok": True, "diary": d.model_dump() if d else None}


# ----- Chat history endpoint -----
@router.get("/chat/{session_id}/history", response_model=dict)
def get_chat_history(session_id: str):
    repo = get_chat_repo()
    msgs = repo.get_session_messages(session_id)
    return {"ok": True, "messages": [m.model_dump() for m in msgs]}


@router.get("/chat/{session_id}/history/{target_date}", response_model=dict)
def get_chat_history_by_date(session_id: str, target_date: str):
    """특정 날짜(YYYY-MM-DD) 기준으로 메시지 조회"""
    repo = get_chat_repo()
    msgs = repo.get_messages_by_date(session_id, target_date)
    return {"ok": True, "messages": [m.model_dump() for m in msgs]}


@router.post("/profile/init/{session_id}", response_model=dict)
def init_profile(session_id: str):
    """Create baby and mother profile records for the given session_id if they don't exist."""
    repo = get_profile_repo()
    created = {"baby": False, "mother": False}
    try:
        if repo.get_baby(session_id) is None:
            repo.upsert_baby(BabyProfile(session_id=session_id))
            created["baby"] = True
    except Exception:
        pass

    try:
        if repo.get_mother(session_id) is None:
            repo.upsert_mother(MotherProfile(session_id=session_id))
            created["mother"] = True
    except Exception:
        pass

    return {"ok": True, "created": created}
