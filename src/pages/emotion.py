# pages/03_감정_분석.py
import streamlit as st
from infra.chat_db import load_messages
from utils.session import get_session_id
from agent.llm import analyze_emotion

st.set_page_config(page_title="감정 분석", page_icon="🧠", layout="centered")
st.title("🧠 엄마의 감정 분석")

session_id = get_session_id()

# 대화 취합
messages = load_messages(session_id)
dialog_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages]) or "대화가 아직 없어요."

if not messages:
    st.info("아직 대화가 없어서 분석할 수 없어요. 먼저 채팅 페이지에서 대화를 나눠주세요.")
else:
    result = analyze_emotion(dialog_text)

    if "error" in result:
        st.error("파싱 오류가 발생했어요. 원문 결과를 보여드릴게요.")
        st.code(result.get("raw", ""))
    else:
        # 요약
        st.subheader("요약")
        st.write(result.get("summary", ""))

        # 감정 라벨
        emotions = result.get("emotions", [])
        if emotions:
            st.caption("감정 라벨")
            st.write(", ".join(emotions))

        # 점수 표
        scores = result.get("scores", {})
        if scores:
            st.caption("감정 점수 (0~1)")
            # 간단 표
            st.table(
                [{"emotion": k, "score": v} for k, v in scores.items()]
            )

        # 근거 문장
        cues = result.get("cues", [])
        if cues:
            st.caption("근거로 확인된 문장들")
            for c in cues:
                st.markdown(f"- {c}")
