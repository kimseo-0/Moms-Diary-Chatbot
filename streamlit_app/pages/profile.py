
import json
from typing import Any
import streamlit as st
from streamlit_app.client_api import get_persona, refresh_persona, init_profile


st.set_page_config(page_title="Profile")


def _pretty_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)

st.title("아기 & 산모 프로필")

# Session ID in the sidebar, fixed to user-123 and read-only
session_id = st.sidebar.text_input("Session ID", value="user-123", disabled=True)

try:
    resp = get_persona(session_id)
except Exception as e:
    st.error(f"조회 실패: {e}")
    st.stop()

if not resp.get("ok"):
    st.error("서버 응답 오류")
    st.stop()

baby = resp.get("baby") or {}
mother = resp.get("mother") or {}
persona = resp.get("persona")
summary = resp.get("summary")

# Baby card
st.subheader("👶 아기 프로필")
if baby:
    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.write("**이름**")
        st.write(baby.get("name") or "-")
    with cols[1]:
        st.write("**주차(week)**")
        st.write(baby.get("week") or "-")
    with cols[2]:
        st.write("**성별**")
        st.write(baby.get("gender") or "U")

    tags = baby.get("tags_json")
    if tags:
        try:
            parsed = json.loads(tags)
            st.write("**태그**: ")
            st.write(", ".join(parsed) if isinstance(parsed, list) else parsed)
        except Exception:
            st.write("**태그**:")
            st.write(tags)

    notes = baby.get("notes")
    if notes:
        st.write("**노트**")
        st.write(notes)

    # _show_metadata(baby.get("created_at"), baby.get("updated_at"))
else:
    st.info("아기 프로필이 없습니다.")

st.markdown("---")

# Mother card
st.subheader("🤰 산모 프로필")
if mother:
    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.write("**이름**")
        st.write(mother.get("name") or "-")
    with cols[1]:
        st.write("**나이**")
        st.write(mother.get("age") or "-")
    with cols[2]:
        st.write("**연락/기타**")
        st.write("-")

    prefs = mother.get("prefs_json")
    if prefs:
        try:
            parsed = json.loads(prefs)
            st.write("**선호사항**")
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    st.write(f"- **{k}**: {v}")
            else:
                st.write(parsed)
        except Exception:
            st.write(prefs)

    medical = mother.get("medical_notes")
    if medical:
        st.write("**의학적 메모**")
        st.write(medical)

    # _show_metadata(mother.get("created_at"), mother.get("updated_at"))
else:
    st.info("산모 프로필이 없습니다.")

st.markdown("---")

# Persona display: summary (text), traits (tags), weekly (per-week summaries)
st.subheader("🧠 Child Persona")

def _extract_persona_dict(persona_raw: Any) -> dict | None:
    if not persona_raw:
        return None
    # If persona is a dict coming from persona_repo.get_latest_child_persona
    if isinstance(persona_raw, dict):
        # persona_json may be stored as a JSON string
        pj = persona_raw.get("persona_json") or persona_raw.get("persona")
        if isinstance(pj, str):
            try:
                return json.loads(pj)
            except Exception:
                pass
        # if dict already contains summary/traits/weekly, return it
        if "summary" in persona_raw or "traits" in persona_raw or "weekly" in persona_raw:
            return persona_raw
        return None

    # If persona is a pydantic model-like
    try:
        if hasattr(persona_raw, "model_dump"):
            return persona_raw.model_dump()
        if hasattr(persona_raw, "dict"):
            return persona_raw.dict()
    except Exception:
        pass

    # If it's a raw JSON string
    if isinstance(persona_raw, str):
        try:
            return json.loads(persona_raw)
        except Exception:
            return None

    return None


persona_dict = _extract_persona_dict(persona)
if persona_dict:
    # summary
    summary_text = persona_dict.get("summary")
    if summary_text:
        st.markdown(f"**요약:**\n\n{summary_text}")

    # traits as tags
    traits = persona_dict.get("traits") or persona_dict.get("tags") or []
    if traits:
        try:
            import html as _html

            chips = "".join([
                f"<span style=\"display:inline-block;background:#eef2ff;color:#0b2e6b;padding:4px 8px;border-radius:12px;margin:4px;font-size:12px\">{_html.escape(str(t))}</span>"
                for t in traits
            ])
            st.markdown(chips, unsafe_allow_html=True)
        except Exception:
            st.write(", ".join([str(t) for t in traits]))

    # weekly summaries
    weekly = persona_dict.get("weekly") or []
    if weekly:
        st.write("**주간 요약:**")
        for item in weekly:
            if isinstance(item, dict):
                wk = item.get("week_start") or item.get("week") or item.get("label") or ""
                summ = item.get("summary") or item.get("text") or str(item)
                st.markdown(f"- **{wk}**: {summ}")
            else:
                st.markdown(f"- {item}")
else:
    st.info("페르소나가 없습니다.")

st.markdown("---")
st.header("액션")
if st.button("페르소나 만들기"):
    try:
        with st.spinner("페르소나 생성 중... 잠시만 기다려주세요"):
            resp = refresh_persona(session_id, background=False)
        if resp.get("ok"):
            st.success("페르소나 생성 완료")
            # reload the page to fetch new persona
            st.experimental_rerun()
        else:
            st.error(f"페르소나 생성 실패: {resp}")
    except Exception as e:
        st.error(f"요청 실패: {e}")