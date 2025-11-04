import streamlit as st
from streamlit_app.client_api import post_expert

st.set_page_config(page_title="Expert QnA")

st.title("전문가 Q&A")
st.markdown("이 페이지는 의료 전문가 에이전트에 바로 질문하고 답변을 받는 전용 채팅입니다.")

# session id in sidebar (read-only default user-123)
session_id = st.sidebar.text_input("Session ID", value="user-123", disabled=True)

if "history" not in st.session_state:
    st.session_state.history = []

# Input form
with st.form(key="expert_form", clear_on_submit=False):
    text = st.text_input("질문 입력", key="expert_input")
    submit = st.form_submit_button("전문가에게 질문")

if submit and text:
    # append user message first so it shows immediately
    st.session_state.history.append(("user", text))
    # call expert endpoint synchronously and show a spinner
    with st.spinner("전문가에게 질문 중... 잠시만 기다려주세요"):
        try:
            resp = post_expert(session_id, text)
            if resp.get("ok") and resp.get("result"):
                result = resp["result"]
                expert_text = result.get("text") or ""
                st.session_state.history.append(("expert", expert_text))
            else:
                st.session_state.history.append(("expert", "서버 오류: 응답이 올바르지 않습니다."))
        except Exception as e:
            st.session_state.history.append(("expert", f"요청 실패: {e}"))

    # clear input box after submit
    try:
        st.session_state["expert_input"] = ""
    except Exception:
        pass

# Render message history (after potential new messages)
col = st.container()
with col:
    for msg in st.session_state.history:
        if msg[0] == "user":
            st.markdown(f"**[질문]:**\n {msg[1]}")
        else:
            st.markdown(f"**[답변]:**\n {msg[1]}")

st.markdown("---")
st.info("참고: 이 페이지는 의료 정보 제공용이며, 개인별 진단·치료는 의료진 상담이 필요합니다.")
