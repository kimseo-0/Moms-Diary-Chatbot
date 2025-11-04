# app/api/http.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.core.io_payload import InputEnvelope, OutputEnvelope, InputPayload, InputMetadata
from app.core.logger import get_logger
from app.core.pydantic_utils import safe_model_dump
from app.graphs.main_graph import compile_app_graph
from functools import lru_cache
from app.core.state import AgentState
from app.core.dependencies import get_diary_repo, get_chat_repo, get_profile_repo
from app.services.diary_repo import DiaryEntry
from app.services.chat_repo import ChatLog
from app.services.profile_repo import BabyProfile, MotherProfile
import json
from pydantic import BaseModel
from app.services.persona_repo import get_latest_child_persona, get_persona_summary
from app.nodes.persona_agent_node import persona_agent_node
from app.nodes.medical_qna_node import medical_qna_node
from app.nodes.baby_smalltalk_node import baby_smalltalk_node
import random
import copy
import io
from pathlib import Path
from PIL import Image
from fastapi import Response

# Import ComfyUI workflow and client from the repo script
# try:
#     from app.confiui.CombineFace_for_junior import CLIENT as COMFY_CLIENT, BASE_WORKFLOW
# except Exception:
#     # If import fails, set to None and raise at runtime
#     COMFY_CLIENT = None
#     BASE_WORKFLOW = None

router = APIRouter()
logger = get_logger(__name__)

@lru_cache(maxsize=1)
def get_app_graph():
    """컴파일된 그래프를 지연 생성하여 import-time 비용을 줄임."""
    return compile_app_graph()


@router.post("/chat", response_model=OutputEnvelope)
def chat(envelope: InputEnvelope) -> OutputEnvelope:
    # 이 세션에 대한 프로필이 존재하는지 확인합니다 (방어적 처리)
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
    # Pydantic 모델에서 받은 metadata를 v1/v2 호환 plain dict로 정규화합니다
        user_meta = safe_model_dump(envelope.payload.metadata)

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
        logger.exception("사용자 메시지 저장 실패: %s", str(e))

    state_in = AgentState(session_id=envelope.session_id, input=envelope)
    state_out = AgentState(**get_app_graph().invoke(state_in))

    try:
        chat_repo = get_chat_repo()
        final = state_out.final
        if final and getattr(final, "result", None):
            res = final.result
            # UI가 타입별로 렌더링할 수 있도록 결과(text, data, meta)를 직렬화합니다
            res_meta = safe_model_dump(res.meta)

            # 데이터 딕셔너리가 있으면 시도해 가져옵니다
            res_data = res.data if hasattr(res, "data") else {}

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
        logger.exception("어시스턴트 메시지 저장 실패: %s", str(e))

    return state_out.final or OutputEnvelope.err("INTERNAL_ERROR", "응답 생성 실패", retryable=False)


@router.post("/chat/expert", response_model=OutputEnvelope)
def chat_expert(envelope: InputEnvelope) -> OutputEnvelope:
    """Expert-only QnA: run medical_qna_node then wrap the expert output via baby_smalltalk_node.wrap_expert

    This endpoint bypasses plan routing and directly invokes the expert node pipeline so the UI
    can present an expert-style answer consistently.
    """
    # ensure profiles exist defensively
    try:
        profile_repo = get_profile_repo()
        if profile_repo.get_baby(envelope.session_id) is None:
            profile_repo.upsert_baby(BabyProfile(session_id=envelope.session_id))
        if profile_repo.get_mother(envelope.session_id) is None:
            profile_repo.upsert_mother(MotherProfile(session_id=envelope.session_id))
    except Exception:
        pass

    state = AgentState(session_id=envelope.session_id, input=envelope)

    try:
        # Run medical QnA node to populate state.metadata with expert_raw and citations
        state = medical_qna_node(state)

        # Return the raw expert text and citations directly (no wrapping) so the UI
        # shows the expert's original wording and tone.
        expert_text = state.metadata.get("expert_raw") if isinstance(state.metadata, dict) else None
        citations = state.metadata.get("citations") if isinstance(state.metadata, dict) else None
        data = {"citations": citations or []}
        if expert_text:
            return OutputEnvelope.ok_expert(expert_text, data=data)
        else:
            return OutputEnvelope.err("INTERNAL_ERROR", "전문가 응답 생성 실패", retryable=False)
    except Exception as e:
        logger.exception("chat_expert failed: %s", str(e))
        return OutputEnvelope.err("INTERNAL_ERROR", "전문가 채팅 처리 중 오류가 발생했습니다.")


class DiarySaveRequest(BaseModel):
    session_id: str
    date: str
    content: str


class CombineFaceRequest(BaseModel):
    positive_prompt: str = "a boy 1 months olds, handsome"
    negative_prompt: str = "blurry, ugly, worst quality"
    image1_filename: str
    image2_filename: str


@router.post("/diary", response_model=dict)
def save_diary(payload: DiarySaveRequest):
    repo = get_diary_repo()
    repo.save_diary(DiaryEntry(session_id=payload.session_id, date=payload.date, content=payload.content))
    return {"ok": True, "date": payload.date}


@router.post("/combineface/generate")
def combineface_generate(payload: CombineFaceRequest):
    # if COMFY_CLIENT is None or BASE_WORKFLOW is None:
    #     raise HTTPException(status_code=500, detail="ComfyUI client not available on server")

    try:
        # Use a deepcopy of the base workflow and set parameters like the script does
        # current_workflow = copy.deepcopy(BASE_WORKFLOW)
        seed = random.randint(1, 1000000000)

        # These node IDs are from the workflow file used in the repo.
        # If the workflow changes, these may need to be updated.
        # current_workflow["3"]["inputs"]["seed"] = seed
        # current_workflow["39"]["inputs"]["text"] = payload.positive_prompt
        # current_workflow["40"]["inputs"]["text"] = payload.negative_prompt
        # current_workflow["13"]["inputs"]["image"] = payload.image1_filename
        # current_workflow["68"]["inputs"]["image"] = payload.image2_filename

        # images = COMFY_CLIENT.get_images(current_workflow)
        # TODO : resource 에 있는 이미지를 더미로 이미지 보내기
        image = Image.new("RGB", (512, 512), color=(73, 109, 137))
        img_byte_arr = io.BytesIO()
        images = {"output_node": [img_byte_arr]}

        # Find the first image bytes we can return
        for node_id, imgs in images.items():
            if imgs:
                # Return the first image bytes as a PNG response
                img_bytes = imgs[0]
                return Response(content=img_bytes, media_type="image/png")

        raise HTTPException(status_code=500, detail="No image produced by ComfyUI workflow")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("combineface generate failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"combineface generation error: {e}")


@router.get("/diary/{session_id}/{target_date}", response_model=dict)
def get_diary(session_id: str, target_date: str):
    repo = get_diary_repo()
    d = repo.get_diary_by_date(session_id, target_date)
    logger.debug("일기 조회(사전): %s", safe_model_dump(d) if d else None)
    if d:  # DB에 일기가 존재하면 즉시 반환
        return {"ok": True, "diary": safe_model_dump(d)}
    
    # 일기가 없으면 diary 노드를 통해 생성 트리거
    metadata = InputMetadata(type="diary", date=target_date, week=None, language="ko")
    payload = InputPayload(text=f"일기 작성해줘", metadata=metadata)
    envelope = InputEnvelope(session_id=session_id, payload=payload)
    
    # diary 노드를 통해 라우팅합니다
    state_in = AgentState(session_id=session_id, input=envelope)
    state_out = AgentState(**get_app_graph().invoke(state_in))

    logger.debug("state_out (다이어리 생성 후): %s", safe_model_dump(state_out))
    
    # 생성 후 일기를 다시 조회합니다
    d = repo.get_diary_by_date(session_id, target_date)
    return {"ok": True, "diary": safe_model_dump(d) if d else None}


@router.get("/chat/{session_id}/history", response_model=dict)
def get_chat_history(session_id: str):
    repo = get_chat_repo()
    msgs = repo.get_session_messages(session_id)
    return {"ok": True, "messages": [safe_model_dump(m) for m in msgs]}


@router.get("/chat/{session_id}/history/{target_date}", response_model=dict)
def get_chat_history_by_date(session_id: str, target_date: str):
    """특정 날짜(YYYY-MM-DD) 기준으로 메시지 조회"""
    repo = get_chat_repo()
    msgs = repo.get_messages_by_date(session_id, target_date)
    return {"ok": True, "messages": [safe_model_dump(m) for m in msgs]}


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


@router.get("/profile/{session_id}", response_model=dict)
def get_profile(session_id: str):
    """Return baby and mother profiles plus latest persona and today's summary."""
    try:
        repo = get_profile_repo()
        baby = repo.get_baby(session_id)
        mother = repo.get_mother(session_id)
    except Exception:
        baby = None
        mother = None

    try:
        persona = get_latest_child_persona(session_id)
    except Exception:
        persona = None

    try:
        from datetime import date

        today = date.today().isoformat()
        summary = get_persona_summary(session_id, today)
    except Exception:
        summary = None

    return {
        "ok": True,
        "baby": safe_model_dump(baby) if baby else None,
        "mother": safe_model_dump(mother) if mother else None,
        "persona": persona,
        "summary": summary,
    }


@router.get("/persona/{session_id}", response_model=dict)
def get_persona(session_id: str):
    """세션의 최신 페르소나와 최신 요약을 반환한다."""
    try:
        persona = get_latest_child_persona(session_id)
    except Exception:
        persona = None

    try:
        # 간단히 오늘 날짜(서버 시간 기준)로 요약 조회
        from datetime import date

        today = date.today().isoformat()
        summary = get_persona_summary(session_id, today)
    except Exception:
        summary = None

    try:
        profile_repo = get_profile_repo()
        baby = profile_repo.get_baby(session_id)
        mother = profile_repo.get_mother(session_id)
        baby_dump = safe_model_dump(baby) if baby else None
        mother_dump = safe_model_dump(mother) if mother else None
    except Exception:
        baby_dump = None
        mother_dump = None

    return {
        "ok": True,
        "persona": persona,
        "summary": summary,
        "baby": baby_dump,
        "mother": mother_dump,
    }


@router.post("/persona/{session_id}/refresh", response_model=dict)
def refresh_persona(session_id: str, background: bool = True):
    """페르소나 재생성 트리거.

    background=True면 비동기 트리거(권장). False면 동기적으로 persona_agent_node를 실행합니다.
    """
    # persona_agent_node expects AgentState; build a minimal one
    from app.core.io_payload import InputEnvelope
    from app.core.state import AgentState

    envelope = InputEnvelope(session_id=session_id, payload=None)
    state = AgentState(session_id=session_id, input=envelope)
    if background:
        try:
            # persona_agent_node will create background task internally
            persona_agent_node(state)
            return {"ok": True, "triggered": "background"}
        except Exception:
            raise HTTPException(status_code=500, detail="failed to trigger background persona generation")
    else:
        try:
            persona_agent_node(state)
            return {"ok": True, "triggered": "sync"}
        except Exception:
            raise HTTPException(status_code=500, detail="failed to run persona generation")
