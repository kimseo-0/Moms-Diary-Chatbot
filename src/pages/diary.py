# pages/diary.py
import streamlit as st
import datetime as dt

from utils.session import get_session_id
from agent.llm import build_diary
from infra.chat_db import init_chat_db, load_messages_by_date
from infra.diary_db import init_diary_db, upsert_diary, load_diaries

st.set_page_config(page_title="Diary", page_icon="📔", layout="centered")
st.title("📔 일기")

# DB 준비
session_id = get_session_id()

# -------------------------------
# 날짜 선택 + 작성하기
# -------------------------------
st.subheader("🗓️ 날짜로 일기 작성")
# c1, c2 = st.columns([2,1])
# with c1:
#     sel_date = st.date_input("일기 날짜 선택", value=dt.date.today())
# with c2:
#     write_clicked = st.button("작성하기", type="primary", use_container_width=True)

sel_date = st.date_input("일기 날짜 선택", value=dt.date.today())
write_clicked = st.button("작성하기", type="primary", use_container_width=True)

def _build_dialog_text(rows):
    if not rows: return ""
    return "\n".join([f"{r['role']}: {r['content']}" for r in rows])

def _split_title_body(md_text: str, default_title: str):
    # 첫 줄에 '# ' 제목이 있으면 분리
    lines = md_text.strip().splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        title = lines[0].lstrip("# ").strip() or default_title
        body = "\n".join(lines[1:]).strip()
        return title, body if body else default_title
    return default_title, md_text

if write_clicked:
    date_str = sel_date.isoformat()
    rows = load_messages_by_date(session_id, date_str)
    if not rows:
        st.info("해당 날짜의 대화 기록이 없어요. 채팅 페이지에서 먼저 대화를 나눠주세요.")
    else:
        dialog_text = _build_dialog_text(rows)
        diary_md = build_diary(dialog_text)  # LLM 호출
        default_title = f"{date_str}의 일기"
        title, body = _split_title_body(diary_md, default_title)
        # DB 저장 (업서트)
        upsert_diary(
            session_id=session_id,
            diary_date=date_str,
            title=title,
            content=body,
            dialog_snapshot=dialog_text
        )
        st.success(f"일기를 저장했어요: {title}")

st.divider()

# -------------------------------
# 히스토리 카드 (최신순)
# -------------------------------
diaries = load_diaries(session_id=session_id, limit=None)
if not diaries:
    st.info("아직 저장된 일기가 없어요. 위에서 날짜를 선택해 작성해 보세요.")
else:
    # 간단한 카드 스타일
    st.markdown("""
    <style>
    .card { border:1px solid #44444433; border-radius:16px; padding:16px 18px;
            box-shadow:0 2px 14px rgba(0,0,0,0.06); background:rgba(255,255,255,0.02); margin-bottom:14px; }
    .muted { opacity: 0.7; font-size: 13px; }
    </style>
    """, unsafe_allow_html=True)

    for d in diaries:   # 이미 최신순 정렬됨
        with st.container(border=True):
            st.markdown(f"### {d['title']}")
            st.markdown(f"<span class='muted'>{d['diary_date']} · 작성 {d['created_at']}</span>", unsafe_allow_html=True)
            # st.markdown("---")
            st.markdown(d["content"])
            with st.expander("대화 스냅샷 보기"):
                st.code(d.get("dialog_snapshot") or "(저장된 스냅샷 없음)")
