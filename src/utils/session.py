# utils/session.py
import streamlit as st

DEFAULT_SESSION_ID = "user-123"

def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = DEFAULT_SESSION_ID
    # 사이드바에서 변경 가능
    with st.sidebar:
        st.session_state["session_id"] = st.text_input(
            "세션 ID", value=st.session_state["session_id"], key="sidebar_session_id"
        )
    return st.session_state["session_id"]
