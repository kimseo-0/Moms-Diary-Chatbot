# pages/02_일기_카드.py
import streamlit as st
from infra.chat_db import init_chat_db, load_messages
from utils.session import get_session_id
from agent.llm import build_diary

st.set_page_config(page_title="일기 카드", page_icon="📔", layout="centered")
st.title("📔 오늘의 일기")

init_chat_db()
session_id = get_session_id()

# 대화 취합
messages = load_messages(session_id)
dialog_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages]) or "대화가 아직 없어요."

# 일기 생성
if messages:
    diary_md = build_diary(dialog_text)
else:
    diary_md = "_아직 대화가 없어 일기를 만들 수 없어요._"

# 카드 느낌 간단 스타일
st.markdown(
    """
    <style>
    .card {
        border: 1px solid #44444433;
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 2px 14px rgba(0,0,0,0.06);
        background: rgba(255,255,255,0.02);
    }
    </style>
    """,
    unsafe_allow_html=True
)

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(diary_md, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
