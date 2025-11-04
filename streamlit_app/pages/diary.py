from __future__ import annotations
import streamlit as st
from datetime import date
from client_api import post_chat, get_diary, save_diary, init_profile

st.subheader("📔 아기 일기 작성")

with st.sidebar:
    st.markdown("### 일기 옵션")
    session_id = st.text_input("Session ID", value="user-123")
    selected_date = st.date_input("날짜", value=date.today())

st.caption("달력에서 날짜를 선택하면 해당 날짜의 일기를 자동으로 불러옵니다. 필요시 새로고침으로 다시 가져올 수 있습니다.")

target_date = selected_date.isoformat()

# --- 간단한 세션별 날짜 캐시 ---
if "diary_cache" not in st.session_state:
    st.session_state.diary_cache = {}
if "cache_session" not in st.session_state:
    st.session_state.cache_session = session_id
elif st.session_state.cache_session != session_id:
    # 세션이 변경되면 안전을 위해 캐시를 비웁니다
    st.session_state.diary_cache = {}
    st.session_state.cache_session = session_id

# 선택한 세션에 대해 프로필이 존재하는지 확인합니다
try:
    if session_id:
        init_profile(session_id)
except Exception:
    pass

def _cache_key(sid: str, d: str) -> str:
    return f"{sid}:{d}"

def load_diary_cached(sid: str, d: str, force: bool = False):
    key = _cache_key(sid, d)
    if not force and key in st.session_state.diary_cache:
        return st.session_state.diary_cache[key]
    with st.spinner("일기 조회 중..."):
        resp = get_diary(sid, d)
    diary = resp.get("diary")
    st.session_state.diary_cache[key] = diary
    return diary

# 수동 새로고침 버튼 (캐시 무시)
refresh = st.button("🔄 새로고침", help="캐시를 무시하고 새로 불러옵니다")

# 날짜 변경 또는 캐시 미스 시 자동 로드
try:
    diary = load_diary_cached(session_id, target_date, force=refresh)
    if diary:
        # 일기 주요 정보 표시
        st.session_state.setdefault("diary_content", diary.get("content", ""))
        st.session_state.setdefault("used_chats", diary.get("used_chats", []))
        st.success(f"{diary.get('date', target_date)}의 일기를 불러왔습니다.")

        # 제목이 있으면 강조해서 표시
        title = diary.get("title")
        if title:
            st.markdown(f"### 📝 {title}")

        # 일기 본문 - container로 표시
        content = diary.get("content", "")
        with st.container(border=True):
            st.write(content)

        # 참고한 대화 Expander
        used = diary.get("used_chats", [])
        if used:
            with st.expander("참고한 대화 보기"):
                for m in used:
                    role = m.get("role", "")
                    created_at = m.get("created_at", "")
                    text = m.get("text", "")
                    st.markdown(
                        f"<div style='margin-bottom:0.5em;'><b>{role}</b> <span style='color:#888;font-size:0.9em;'>({created_at})</span><br>{text}</div>",
                        unsafe_allow_html=True,
                    )
    else:
        st.session_state.setdefault("diary_content", "")
        st.info("해당 날짜는 일기가 없어요!")
except Exception as e:
    st.error(f"일기 조회 중 오류: {e}")
