# pages/baby.py
import json
import datetime as dt
import streamlit as st

from infra.db.baby_db import load_baby_profile, upsert_baby_profile
from utils.session import get_session_id

st.set_page_config(page_title="아기 정보", page_icon="👶", layout="centered")
st.title("👶 아기 정보")

# --- helpers: notes <-> sections ------------------------------------------------
SECTIONS = ["증상", "검진", "접종", "생활", "영양", "출산준비"]

def parse_notes_sections(notes: str) -> dict:
    """[증상] ... [검진] ... 형태의 notes를 섹션별 dict로 파싱"""
    out = {k: "" for k in SECTIONS}
    if not notes:
        return out
    cur = None
    buf = []
    def flush():
        nonlocal cur, buf
        if cur:
            out[cur] = "".join(buf).strip()
        buf = []
    for line in notes.splitlines(keepends=True):
        line_stripped = line.strip()
        if line_stripped.startswith("[") and line_stripped.endswith("]") and line_stripped[1:-1] in SECTIONS:
            flush()
            cur = line_stripped[1:-1]
        else:
            buf.append(line)
    flush()
    return out

def build_notes_from_sections(d: dict, tail: str = "") -> str:
    parts = []
    for k in SECTIONS:
        parts.append(f"[{k}]\n{(d.get(k) or '').strip()}\n")
    if tail:
        parts.append(tail.strip())
    return "\n".join(parts).strip()

# --- init/load ------------------------------------------------------------------
session_id = get_session_id()
profile = load_baby_profile(session_id)

# state: view/edit toggle
# if "baby_edit_mode" not in st.session_state:
#     st.session_state.baby_edit_mode = False

# tags 파싱
try:
    current_tags = json.loads(profile.get("tags", "[]")) or []
except Exception:
    current_tags = []

# notes → 섹션 분해 (보기/수정에 공용 사용)
sections = parse_notes_sections(profile.get("notes", ""))

# --- VIEW MODE ------------------------------------------------------------------
def render_view(p):
    with st.container(border=True):
        st.subheader("👶 기본 프로필")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**태명**: {p.get('nickname','') or '—'}")
        with col2:
            st.markdown(f"**성별**: {p.get('sex','모름')}")
        with col3:
            st.markdown(f"**임신 주차**: {int(p.get('week',0))}주 {int(p.get('day',0))}일")

        tag_text = ", ".join(current_tags) if current_tags else "—"
        st.markdown(f"**성격 키워드**: {tag_text}")

        c1, c2 = st.columns(2)
        lmp, due = p.get("lmp_date"), p.get("due_date")
        with c1:
            st.markdown(f"**마지막 생리 시작일**: {lmp or '—'}")
        with c2:
            st.markdown(f"**출산 예정일**: {due or '—'}")

        c3, c4, c5 = st.columns(3)
        with c3:
            st.markdown(f"**병원**: {p.get('hospital','') or '—'}")
        with c4:
            st.markdown(f"**주치의**: {p.get('doctor','') or '—'}")
        with c5:
            bt = p.get("mom_blood_type","") or "—"
            rh = p.get("mom_rh","") or "—"
            st.markdown(f"**엄마 혈액형/Rh**: {bt} {rh}")

    st.subheader("📒 기록")
    for key, label in [("증상","🩺 증상 / 컨디션"), ("검진","📅 검진 일정/결과"),
                       ("접종","💉 접종/항체"), ("생활","💤 생활 메모"),
                       ("영양","🍎 영양 메모"), ("출산준비","🍼 출산/육아 준비")]:
        with st.expander(f"{label}", expanded=False):
            txt = sections.get(key) or "—"
            st.markdown(txt.replace("\n","  \n"))

    # 진행 요약
    st.divider()
    st.subheader("📊 임신 진행 요약")
    week, day = int(p.get("week", 0)), int(p.get("day", 0))
    total_days = week * 7 + day
    trimester = "1분기 (1–13주)" if week <= 13 else "2분기 (14–27주)" if week <= 27 else "3분기 (28–40주)"
    st.write(f"- 현재 임신 주차: **{week}주 {day}일** (총 {total_days}일)")
    st.write(f"- 진행 시기: **{trimester}**")
    if p.get("lmp_date"):
        try:
            calc_due = dt.date.fromisoformat(p["lmp_date"]) + dt.timedelta(days=280)
            st.write(f"- LMP 기준 예정일: **{calc_due.isoformat()}**")
        except Exception:
            pass
    if p.get("due_date"):
        st.write(f"- 저장된 출산 예정일: **{p['due_date']}**")
    st.progress(min(total_days / 280.0, 1.0), text=f"임신 진행률 {int(total_days/2.8)}%")

# --- EDIT MODE ------------------------------------------------------------------
def render_edit(p):
    DEFAULT_TAGS = ["차분함","활발함","호기심많음","애교많음","장난기","느긋함","껌딱지","먹보","잠꾸러기"]

    with st.form("baby_form", border=True):
        st.subheader("👶 기본 프로필 수정")
        c1, c2 = st.columns([2,1])
        with c1:
            nickname = st.text_input("태명", value=p.get("nickname",""), placeholder="예: 콩이")
        with c2:
            sex = st.segmented_control("성별", ["남자","여자","모름"], default=p.get("sex","모름"))

        # tags = st.multiselect("성격 키워드", options=DEFAULT_TAGS, default=current_tags)
        
        # 한 줄에 3개씩 배치
        cols_per_row = 3
        selected_tags = set(current_tags)

        st.markdown("**성격 키워드 선택**")
        for i in range(0, len(DEFAULT_TAGS), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, tag in enumerate(DEFAULT_TAGS[i:i+cols_per_row]):
                with cols[j]:
                    active = tag in selected_tags
                    # 토글 스위치 버튼
                    toggle = st.checkbox(tag, value=active, key=f"tag_{tag}")
                    if toggle:
                        selected_tags.add(tag)
                    else:
                        selected_tags.discard(tag)

        tags = list(selected_tags)

        c3, c4 = st.columns(2)
        with c3:
            week = st.number_input("임신 주차", 0, 42, int(p.get("week",0)), step=1)
        with c4:
            day  = st.number_input("추가 일수(0~6)", 0, 6, int(p.get("day",0)), step=1)

        c5, c6 = st.columns(2)
        lmp_val = p.get("lmp_date")
        due_val = p.get("due_date")
        with c5:
            lmp = st.date_input("마지막 생리 시작일", value=dt.date.fromisoformat(lmp_val) if lmp_val else None)
        with c6:
            due = st.date_input("출산 예정일", value=dt.date.fromisoformat(due_val) if due_val else None)

        st.subheader("🏥 엄마 & 병원")
        c7, c8 = st.columns(2)
        with c7:
            mom_blood = st.selectbox("엄마 혈액형", ["","A","B","AB","O"], index=["","A","B","AB","O"].index(p.get("mom_blood_type","")))
        with c8:
            mom_rh = st.selectbox("Rh", ["","+","-"], index=["","+","-"].index(p.get("mom_rh","")))
        
        c9, c10 = st.columns(2)
        with c9:
            hospital = st.text_input("병원명", value=p.get("hospital",""))
        with c10:
            doctor = st.text_input("주치의", value=p.get("doctor",""))

        st.subheader("📒 기록 수정")
        s_sym = st.text_area("🩺 증상 / 컨디션", value=sections.get("증상",""))
        s_chk = st.text_area("📅 검진 일정/결과", value=sections.get("검진",""))
        s_vac = st.text_area("💉 접종/항체", value=sections.get("접종",""))
        s_lif = st.text_area("💤 생활 메모", value=sections.get("생활",""))
        s_nut = st.text_area("🍎 영양 메모", value=sections.get("영양",""))
        s_del = st.text_area("🍼 출산/육아 준비", value=sections.get("출산준비",""))

        # c_ok, c_cancel = st.columns([1,1])
        # with c_ok:
        #     saved = st.form_submit_button("💾 저장", type="primary")
        # with c_cancel:
        #     cancelled = st.form_submit_button("취소")
        
        saved = st.form_submit_button("💾 저장", type="primary")

    if saved:
        notes = build_notes_from_sections({
            "증상": s_sym,
            "검진": s_chk,
            "접종": s_vac,
            "생활": s_lif,
            "영양": s_nut,
            "출산준비": s_del
        }, tail="")
        upsert_baby_profile(
            session_id,
            {
                "nickname": nickname.strip(),
                "sex": sex,
                "week": int(week),
                "day": int(day),
                "tags": tags,
                "lmp_date": lmp.isoformat() if lmp else None,
                "due_date": due.isoformat() if due else None,
                "hospital": hospital.strip(),
                "doctor": doctor.strip(),
                "mom_blood_type": mom_blood,
                "mom_rh": mom_rh,
                "notes": notes,
                # 아래 필드는 baby_db 스키마에 있지만 여기선 사용 안 함
                "allergies": "", "meds": "", "supplements": "",
            },
        )
        st.success("저장했어요.")
        st.session_state.baby_edit_mode = False
        st.rerun()

    # if cancelled:
    #     st.info("수정을 취소했어요.")
    #     st.session_state.baby_edit_mode = False
    #     st.rerun()

# --- header buttons -------------------------------------------------------------
# btn_cols = st.columns([1,1,6])
# with btn_cols[0]:
#     if not st.session_state.baby_edit_mode and st.button("✏️ 수정하기", use_container_width=True):
#         st.session_state.baby_edit_mode = True
#         st.rerun()
# with btn_cols[1]:
#     if st.session_state.baby_edit_mode and st.button("👀 보기로", use_container_width=True):
#         st.session_state.baby_edit_mode = False
#         st.rerun()

# --- render ---------------------------------------------------------------------
# if st.session_state.baby_edit_mode:
#     render_edit(profile)
# else:
#     render_view(profile)

render_edit(profile)