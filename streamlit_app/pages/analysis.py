# ui/streamlit_app/pages/emotion.py
import streamlit as st
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from collections import defaultdict, Counter
import re
import koreanize_matplotlib

# 프로젝트 레이어 의존
try:
    # 권장: dependencies에서 주입한 repo 사용
    from app.core.dependencies import get_chat_repo
    chat_repo = get_chat_repo()
    HAVE_REPO = True
except Exception:
    HAVE_REPO = False

st.title("🧠 감정 분석")

KST = ZoneInfo("Asia/Seoul")
today = datetime.now(tz=KST).date()
default_start = date(2025, 10, 31)  # 요청: 10월 31일부터
default_end = today

with st.sidebar:
    st.subheader("🔎 분석 범위")
    start_date = st.date_input("시작일", value=default_start, max_value=today)
    end_date = st.date_input("종료일", value=default_end, min_value=start_date, max_value=today)
    session_id = st.text_input("세션 ID", value=st.session_state.get("session_id", "user-123"))
    st.caption("※ 사용자의 채팅 텍스트만 사용하며 간단한 키워드 휴리스틱으로 점수를 산출합니다.")

# ------------------------------------------------------------------------------
# 1) 데이터 로딩
# ------------------------------------------------------------------------------
def load_chats(session_id: str, start: date, end: date):
    """
    repo 표준이 서로 다를 수 있어 보수적으로 구현:
    - 최근 메시지 N개를 가져와서 created_at으로 로컬 필터링
    - role == 'user' 만 분석
    """
    if not HAVE_REPO:
        return []
    # 넉넉히 가져와서 필터 (필요시 repo에 기간조회 함수 추가 권장)
    rows = chat_repo.get_recent_messages(session_id=session_id, limit=2000)
    out = []
    for m in rows:
        # created_at 문자열 → date
        created = getattr(m, "created_at", None) or getattr(m, "createdAt", None) or getattr(m, "created", None)
        text = getattr(m, "text", None) or getattr(m, "message", None)
        role = getattr(m, "role", "user")
        if not created or not text:
            continue
        try:
            # ISO-8601 or sqlite DATETIME
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except Exception:
            # fallback: treat as naive
            dt = datetime.strptime(str(created), "%Y-%m-%d %H:%M:%S")
        d = dt.astimezone(KST).date()
        if start <= d <= end and role == "user":
            out.append({"date": d, "text": text})
    return out

data = load_chats(session_id, start_date, end_date)

if not data:
    st.info("분석할 사용자 채팅이 없습니다. (범위/세션ID를 확인해 주세요)")
    st.stop()

# ------------------------------------------------------------------------------
# 2) EPDS 더미 스코어링
#    - 실제 EPDS(10문항, 각 0~3점, 총 30점)과 1:1 대응하지 않고
#      텍스트 키워드 기반 휴리스틱으로 '비공식 추정 점수'를 산출(연구/의료 목적 아님).
# ------------------------------------------------------------------------------
NEG_PACKS = {
    # 슬픔/우울
    "depressed":  [r"우울", r"슬프", r"눈물", r"울컥", r"힘들", r"다운", r"의욕 없", r"무기력"],
    # 불안/걱정
    "anxious":    [r"불안", r"걱정", r"초조", r"긴장", r"두려", r"무섭"],
    # 짜증/분노
    "irritated":  [r"짜증", r"화나", r"빡치", r"열받", r"예민"],
    # 절망/죄책
    "hopeless":   [r"절망", r"희망 없", r"포기", r"내 탓", r"죄책"],
    # 수면/피로
    "sleep":      [r"잠이 안", r"불면", r"깨", r"피곤", r"기진맥진", r"녹초"],
    # 식사/식욕
    "appetite":   [r"입맛 없", r"식욕 없", r"못 먹", r"토할 것"],
    # 자기비난/무가치감
    "self":       [r"난 왜", r"못하겠", r"무가치", r"쓸모 없", r"존재감 없"],
}

POS_PACKS = {
    # 즐거움/보람
    "positive":   [r"행복", r"기쁨", r"뿌듯", r"괜찮", r"좋았", r"고마", r"사랑", r"응원", r"회복"],
    # 도움/지지
    "support":    [r"도움", r"지지", r"위로", r"같이 해", r"같이해", r"함께", r"고맙"],
}

def score_text_epds_dummy(text: str) -> dict:
    """
    더미 EPDS 유사 스코어:
    - 부정 카테고리 매치: 각 카테고리 0~3점 (중복 키워드 가중)
    - 긍정 카테고리 매치: 총점에서 최대 0~3점 완충(-min(3, 매치수))
    - 최종 0~30 범위로 클리핑 (대략적)
    ※ 실제 EPDS 대체가 아님
    """
    t = text.lower()
    neg_total = 0
    neg_breakdown = {}
    for name, pats in NEG_PACKS.items():
        cnt = sum(1 for p in pats if re.search(p, t))
        # 강도: 0~3
        score = min(3, cnt)
        neg_breakdown[name] = score
        neg_total += score

    pos_hits = sum(1 for pats in POS_PACKS.values() for p in pats if re.search(p, t))
    pos_cushion = min(3, pos_hits)

    raw = max(0, neg_total - pos_cushion)
    final = max(0, min(30, raw))  # 0~30 클리핑
    return {"score": final, "neg": neg_breakdown, "pos_hits": pos_hits}

# 날짜별 스코어 집계
daily_scores = defaultdict(list)
for row in data:
    s = score_text_epds_dummy(row["text"])
    daily_scores[row["date"]].append(s["score"])

daily_agg = []
for d in sorted(daily_scores.keys()):
    scores = daily_scores[d]
    daily_agg.append({
        "date": d,
        "count": len(scores),
        "avg_score": round(sum(scores) / len(scores), 2),
        "max_score": max(scores),
    })

# ------------------------------------------------------------------------------
# 3) UI 렌더링
# ------------------------------------------------------------------------------
st.subheader("📆 날짜별 감정 분석")
col1, col2, col3 = st.columns(3)
avg_overall = round(sum(x["avg_score"] for x in daily_agg) / len(daily_agg), 2)
max_overall = max(x["max_score"] for x in daily_agg)
count_msgs = sum(x["count"] for x in daily_agg)

col1.metric("평균 점수(기간)", f"{avg_overall} / 30")
col2.metric("최대 점수(기간 최고)", f"{max_overall} / 30")
col3.metric("분석 메시지 수", f"{count_msgs}건")

st.caption("※ 13점 이상은 실제 EPDS에서 고위험으로 간주되는 경향이 있으나 "
            "정확한 평가는 의료진 상담 및 정식 검사를 통해 진행하세요.")

# 라인 차트
import pandas as pd
import matplotlib.pyplot as plt

df = pd.DataFrame(daily_agg)
st.dataframe(df, hide_index=True, use_container_width=True)

fig, ax = plt.subplots()
ax.plot(df["date"], df["avg_score"], marker="o")
ax.set_title("날짜별 평균 점수")
ax.set_xlabel("날짜")
ax.set_ylabel("평균 점수 (0~30)")
ax.grid(True, alpha=0.3)
st.pyplot(fig)

# 하이라이트 알림
HIGH_RISK_THRESHOLD = 13
alerts = [f"• {row['date']} : 평균 {row['avg_score']}점 (메시지 {row['count']}건)" 
          for row in daily_agg if row["avg_score"] >= HIGH_RISK_THRESHOLD]
if alerts:
    st.error("🚨 고위험 의심 일자:\n" + "\n".join(alerts))
else:
    st.success("최근 기간 내 고위험 의심 일자가 없습니다.")

# 원문 미리보기(선택)
with st.expander("🔎 원문 미리보기 (사용자 메시지)"):
    for row in sorted(data, key=lambda x: (x["date"])):
        st.markdown(f"- **{row['date']}** : {row['text']}")

st.info(
    "정확한 평가는 의료진 상담 및 정식 검사를 통해 진행하세요."
)
