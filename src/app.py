# app.py
# uv add openai python-dotenv streamlit
# uv add streamlit==1.49.1
# .env: OPENAI_API_KEY=...
# 실행: streamlit run src/app.py
import streamlit as st
from infra.db.chat_db import init_chat_db
from infra.db.baby_db import init_baby_db
from infra.db.diary_db import init_diary_db, upsert_diary, load_diaries

init_chat_db()
init_baby_db()
init_diary_db()
st.set_page_config(page_title="콩이 서비스", page_icon="🍼", layout="centered")

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
    st.Page(
        page="pages/emotion.py",
        title="Emotion Analysis",
        icon="🧠",
        url_path="emotion",
    ),
    st.Page(
        page="pages/baby.py",
        title="Baby",
        icon="🍼",
        url_path="baby",
    ),
]

nav = st.navigation(pages)
nav.run()
