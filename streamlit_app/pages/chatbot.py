# streamlit_app/pages/chatbot.py
from __future__ import annotations
import streamlit as st
from typing import Dict, Any
import json
from client_api import post_chat
from client_api import get_chat_history_by_date, init_profile
from datetime import date as _date

def render_assistant(result: Dict[str, Any]):
    meta = result.get("meta", {})
    rtype = meta.get("type")
    text = result.get("text", "")

    if rtype == "chat":
        # Special UI handling: when the diary node returns a chat-type response
        # indicating there is no conversation data for creating a diary,
        # show a prominent warning instead of a normal chat bubble.
        source = meta.get("source", "")
        if source == "diary_node" and ("대화 내용이 없" in text or "작성할 대화 내용이 없어요" in text):
            st.warning(text)
        else:
            st.write(text)
    elif rtype == "expert_answer":
        st.markdown(f"**🩺 전문가 답변**\n\n{text}")
        data = result.get("data", {})
        if data.get("raw"):
            with st.expander("전문가 원문 보기"):
                st.write(data["raw"])
    elif rtype == "diary_entry":
        st.markdown(f"**📓 오늘의 일기**")
        data = result.get("data", {})
        st.info(f"날짜: {data.get('diary', {}).get('date','')}")
        st.write(data.get("diary", {}).get("content", ""))
        # Show core chats used to create the diary in an expander/toggle
        used = data.get("used_chats") or []
        if used:
            with st.expander("참고한 대화 보기"):
                for m in used:
                    role = m.get("role", "")
                    created = m.get("created_at", "")
                    st.markdown(f"- **{role}** ({created}): {m.get('text','')}")
    elif rtype == "safety_alert":
        st.error(f"🚨 {text}")
    else:
        st.write(text or "…")

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

    # Ensure profiles exist for this session (call backend init)
    try:
        if session_id:
            init_profile(session_id)
    except Exception:
        # ignore init failures
        pass

    # Show the currently selected chat date in the UI title area
    try:
        st.markdown(f"**현재 보고 있는 채팅 날짜:** {target_date}")
    except Exception:
        pass

    # --- Simple cache for chat histories per (session_id, date) ---
    if "chat_cache" not in st.session_state:
        st.session_state["chat_cache"] = {}
    if "chat_cache_session" not in st.session_state:
        st.session_state["chat_cache_session"] = session_id
    elif st.session_state["chat_cache_session"] != session_id:
        # Session switched: clear chat cache
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
            # Return a shallow copy so the live state can diverge without mutating cache
            return list(st.session_state["chat_cache"][key])
        resp = get_chat_history_by_date(sid, d)
        items = _build_messages_from_response(resp)
        st.session_state["chat_cache"][key] = list(items)
        return items

    # Manual refresh button (bypass cache)
    refresh = st.button("🔄 채팅 새로고침", help="캐시를 무시하고 다시 불러옵니다")

    # Load when session/date changes or when refresh requested
    loaded_key = st.session_state.get("loaded_session_date")
    if loaded_key != (session_id, target_date) or refresh:
        try:
            items = load_chat_cached(session_id, target_date, force=refresh)
        except Exception:
            items = []
        st.session_state["messages"] = list(items)
        st.session_state["loaded_session_date"] = (session_id, target_date)

    # 1) 과거 메시지 먼저 렌더
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
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
        with st.chat_message("user"):
            st.markdown(user_text)

        # 히스토리에 유저 메시지 먼저 저장
        st.session_state["messages"].append({
            "role": "user",
            "content": user_text,
        })

        # 3) 어시스턴트 호출 + 렌더
        with st.chat_message("assistant"):
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
                # Update cache for current (session_id, date)
                try:
                    st.session_state["chat_cache"][
                        f"{session_id}:{target_date}"
                    ] = list(st.session_state["messages"])  # shallow copy
                except Exception:
                    pass

if __name__ == "__main__":
    main()
