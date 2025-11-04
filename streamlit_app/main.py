# streamlit 앱 진입점
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="콩이와 하루",
    page_icon="🍼",
    layout="centered"
)

pages = [
    st.Page(
        page="pages/chatbot.py",
        title="Chatbot",
        icon="💬",
        default=True,
        url_path="chat",
    ),
    st.Page(
        page="pages/diary.py",
        title="Diary",
        icon="📔",
        url_path="diary",
    ),
    st.Page(
        page="pages/profile.py",
        title="Profile",
        icon="👤",
        url_path="profile",
    ),
    st.Page(
        page="pages/expert_qna.py",
        title="Expert QnA",
        icon="🩺",
        url_path="expert",
    ),
    st.Page(
        page="pages/analysis.py",
        title="Analysis",
        icon="📊",
        url_path="analysis",
    ),
    st.Page(
        page="pages/face_image.py",
        title="Face Image",
        icon="🎨",
        url_path="face_image",
    ),
]

nav = st.navigation(pages)
nav.run()
