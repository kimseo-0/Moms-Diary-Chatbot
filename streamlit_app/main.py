# uv run streamlit run streamlit_app/main.py
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
        url_path="chat"
    ),
    st.Page(
        page="pages/diary.py",
        title="Diary",
        icon="📔",
        url_path="diary",
    ),
    # st.Page(
    #     page="pages/emotion.py",
    #     title="Emotion Analysis",
    #     icon="🧠",
    #     url_path="emotion",
    # ),
    # st.Page(
    #     page="pages/baby.py",
    #     title="Baby",
    #     icon="🍼",
    #     url_path="baby",
    # ),
]

nav = st.navigation(pages)
nav.run()
