import streamlit as st

from infra.chat_db import init_chat_db, load_messages, save_message
from utils.session import get_session_id
from agent.chat import send_chat

session_id = get_session_id()

st.set_page_config(page_title="Chat", page_icon="🗨️", layout="centered")
st.title("🗨️ Chat")

profile = {
    "user": "./resources/user.png",
    "assistant"  : "./resources/chatbot2.png"
}
# ----------------------------
# 0) 세션 히스토리 초기화
# ----------------------------
if "messages" not in st.session_state:
    init_chat_db()
    st.session_state["messages"] = load_messages(session_id)

# ----------------------------
# 1) 과거 히스토리 렌더링
# ----------------------------
for chat in st.session_state["messages"]:
    name = chat["role"]
    avatar = profile[name]
    st.chat_message(name=name, avatar=avatar).markdown(chat["content"])

# ----------------------------
# 2) 입력 받기
# ----------------------------
user_text = st.chat_input("메시지를 입력하세요...")
if user_text:
    # 2-1) 화면 출력
    st.chat_message(name="user", avatar=profile["user"]).markdown(user_text)

    # 2-2) 세션 히스토리 & DB에 즉시 반영
    st.session_state["messages"].append({"role": "user", "content": user_text})
    # save_message(session_id, "user", user_text)    # ← chat_db.save_message 사용

    # 2-3) 어시스턴트 자리
    with st.chat_message(name="assistant", avatar=profile["assistant"]):
        container = st.empty()
        with container:
            spin_text = f"{profile.get('nickname')}가 생각하는 중이에요..." if profile.get('nickname') else "생각하는 중이에요..."
            with st.spinner(spin_text):
                answer = send_chat(user_text)      # 동기 함수라고 가정 (비동기면 await/stream 처리)
            st.markdown(answer)

    # 2-4) 어시스턴트 응답도 세션 & DB에 반영
    st.session_state["messages"].append({"role": "assistant", "content": answer})
    # save_message(session_id, "assistant", answer)