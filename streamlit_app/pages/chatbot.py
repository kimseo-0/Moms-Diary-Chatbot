from __future__ import annotations
import streamlit as st
from typing import Dict, Any
import json
from client_api import post_chat
from client_api import get_chat_history_by_date, init_profile
from datetime import date as _date
import base64
from pathlib import Path

def render_assistant(result: Dict[str, Any]):
    meta = result.get("meta", {})
    rtype = meta.get("type")
    text = result.get("text", "")

    if rtype == "chat":
        # 다이어리 노드가 '채팅 없음'을 알리는 chat 타입을 반환할 경우
        # 일반 채팅 버블 대신 경고로 표시합니다.
        source = meta.get("source", "")
        if source == "diary_node" and ("대화 내용이 없" in text or "작성할 대화 내용이 없어요" in text):
            st.warning(text)
        else:
            st.write(text)
    elif rtype == "expert_answer":
        # 전문가 답변은 카드 형태로 강조 출력
        st.markdown(f"**🩺 전문가 답변**\n\n{text}")
        data = result.get("data", {})
        if data.get("raw"):
            with st.expander("전문가 원문 보기"):
                st.write(data["raw"])
    elif rtype == "diary_entry":
        # 일기 형태 응답 처리
        st.markdown(f"**📓 오늘의 일기**")
        data = result.get("data", {})
        st.info(f"날짜: {data.get('diary', {}).get('date','')}")
        st.write(data.get("diary", {}).get("content", ""))
        # 참고한 대화 보기
        used = data.get("used_chats") or []
        if used:
            with st.expander("참고한 대화 보기"):
                for m in used:
                    role = m.get("role", "")
                    created = m.get("created_at", "")
                    st.markdown(f"- **{role}** ({created}): {m.get('text','')}")
    elif rtype == "safety_alert":
        # 안전 관련 경고는 에러 박스로 표시
        st.error(f"🚨 {text}")
    else:
        st.write(text or "…")

def _load_avatar(filename: str, fallback: str):
    """Try to load `filename` from likely `resources` folders and return a data URI or fallback emoji.

    Checks (in order):
    - streamlit_app/resources (relative to this file)
    - repository root `resources` (two levels up)
    """
    try:
        here = Path(__file__).resolve()
        candidates = [
            here.parent.parent / "resources",
            here.parents[2] / "resources",
        ]
        for res_dir in candidates:
            p = res_dir / filename
            if p.exists():
                data = p.read_bytes()
                suf = p.suffix.lower()
                mime = "image/png"
                if suf in (".jpg", ".jpeg"):
                    mime = "image/jpeg"
                elif suf == ".webp":
                    mime = "image/webp"
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return fallback

def main():
    st.subheader("💬 엄마-아기 챗봇")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []  # [{role:"user|assistant", "content":str, "result":dict|None}]

    # 사이드바 옵션(여기 변경해도 메시지 안날아가요)
    with st.sidebar:
        st.markdown("### 대화 옵션")
        session_id = st.text_input("세션 ID", value="user-123")
        selected_date = st.date_input("날짜", value=_date.today())
        target_date = selected_date.isoformat()

    # 이 세션에 대한 프로필이 존재하는지 확인합니다 (백엔드 초기화 호출)
    try:
        if session_id:
            init_profile(session_id)
    except Exception:
        # 초기화 실패는 무시합니다
        pass

    # UI 타이틀 영역에 현재 선택된 채팅 날짜를 표시합니다
    try:
        st.markdown(f"**현재 보고 있는 채팅 날짜:** {target_date}")
    except Exception:
        pass

    # --- (session_id, date) 기준 간단한 채팅 캐시 ---
    if "chat_cache" not in st.session_state:
        st.session_state["chat_cache"] = {}
    if "chat_cache_session" not in st.session_state:
        st.session_state["chat_cache_session"] = session_id
    elif st.session_state["chat_cache_session"] != session_id:
    # 세션이 바뀌면 채팅 캐시를 비웁니다
        st.session_state["chat_cache"] = {}
        st.session_state["chat_cache_session"] = session_id

    def _chat_key(sid: str, d: str) -> str:
        return f"{sid}:{d}"

    def _build_messages_from_response(resp: Dict[str, Any]):
        items = []
        if resp.get("ok"):
            for m in resp.get("messages", []):
                role = m.get("role", "user")
                if role == "assistant":
                    raw = m.get("meta_json") or m.get("meta") or m.get("metaJson") or ""
                    try:
                        res = json.loads(raw) if raw else {}
                    except Exception:
                        res = {}
                    if res:
                        items.append({
                            "role": "assistant",
                            "content": res.get("text", ""),
                            "result": res,
                        })
                    else:
                        items.append({
                            "role": "assistant",
                            "content": m.get("text", ""),
                        })
                else:
                    items.append({
                        "role": role,
                        "content": m.get("text", ""),
                    })
        return items

    def load_chat_cached(sid: str, d: str, force: bool = False):
        key = _chat_key(sid, d)
        if (not force) and key in st.session_state["chat_cache"]:
            # 캐시를 직접 변경하지 않도록 얕은 복사본을 반환합니다
            return list(st.session_state["chat_cache"][key])
        resp = get_chat_history_by_date(sid, d)
        items = _build_messages_from_response(resp)
        st.session_state["chat_cache"][key] = list(items)
        return items

    # 수동 새로고침 버튼 (캐시 우회)
    refresh = st.button("🔄 채팅 새로고침", help="캐시를 무시하고 다시 불러옵니다")

    # 세션/날짜 변경 또는 새로고침 요청 시 로드합니다
    loaded_key = st.session_state.get("loaded_session_date")
    if loaded_key != (session_id, target_date) or refresh:
        try:
            items = load_chat_cached(session_id, target_date, force=refresh)
        except Exception:
            items = []
        st.session_state["messages"] = list(items)
        st.session_state["loaded_session_date"] = (session_id, target_date)

    # -- 아바타 로드 (resources 폴더 내 이미지 우선, 없으면 이모지로 대체) --
    assistant_avatar = _load_avatar("assistant.png", "🤖")
    user_avatar = _load_avatar("user.png", "🧑‍🍼")

    # 1) 과거 메시지 먼저 렌더
    for msg in st.session_state["messages"]:
        avatar = assistant_avatar if msg.get("role") == "assistant" else user_avatar
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant" and msg.get("result"):
                render_assistant(msg["result"])
            else:
                st.markdown(msg["content"])

    # 2) 입력 수신
    # 채팅은 오직 오늘 날짜에만 허용
    is_today = (target_date == _date.today().isoformat())
    if not is_today:
        st.info("오늘이 아닌 날짜는 채팅할 수 없습니다.")
        user_text = None
    else:
        user_text = st.chat_input("엄마의 메시지를 입력하세요…")

    if user_text:
        # 방금 입력한 사용자 메시지를 즉시 화면에 표시
        with st.chat_message("user", avatar=user_avatar):
            st.markdown(user_text)

        # 히스토리에 유저 메시지 먼저 저장
        st.session_state["messages"].append({
            "role": "user",
            "content": user_text,
        })

        # 3) 어시스턴트 호출 + 렌더
        with st.chat_message("assistant", avatar=assistant_avatar):
            with st.spinner("아기가 생각 중…"):
                resp = post_chat(
                    session_id=session_id,
                    text=user_text,
                    date=target_date,
                )

            if not resp.get("ok", False):
                err_msg = resp.get("error", {}).get("message", "unknown")
                st.error(f"오류: {err_msg}")
                # 실패도 히스토리에 남겨두기
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": f"오류: {err_msg}",
                })
            else:
                result = resp.get("result", {})
                render_assistant(result)
                # 히스토리에 어시스턴트 메시지 저장(렌더 후 저장)
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": result.get("text", ""),
                    "result": result,
                })
                # 현재 (session_id, date)에 대한 캐시를 업데이트합니다
                try:
                    st.session_state["chat_cache"][
                        f"{session_id}:{target_date}"
                    ] = list(st.session_state["messages"])  # shallow copy
                except Exception:
                    pass

if __name__ == "__main__":
    main()
