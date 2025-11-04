"""
간단한 persona 관련 도구들

구현 원칙:
- 복잡한 공통 캐시 파일 대신 이 모듈 내에 최소한의 로컬 캐시(dict+ttl)를 둡니다.
- 직관적이고 이해하기 쉬운 코드 지향. 주석은 한글로 최소한만 추가.

기능(초기):
- summarize_week_tool: 주어진 채팅 목록으로 간단 요약(룰 기반, LLM 호출은 추후 확장)
- get_or_build_history_block: 캐시 우선으로 weekly summaries를 조립

주의: 실제 채팅 저장소 조회 함수는 프로젝트의 chat_repo 등에서 제공되므로
현재는 호출 지점만 만들어 두고, 실제 통합은 나중에 연결합니다.
"""
from __future__ import annotations
import functools
from typing import List, Dict, Any, Optional
from app.services import persona_repo
from app.core.dependencies import get_chat_repo

# 간단화: 표준 라이브러리의 lru_cache를 사용해 캐시 처리합니다.
# TTL이 필요하면 추후 확장할 수 있지만, 우선은 lru_cache(maxsize=128)를 사용합니다.
from functools import lru_cache
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.tooling import get_llm


def summarize_week_tool(session_id: str, week_start: str, chats: List[Dict[str, Any]], max_chars: int = 800) -> Dict[str, Any]:
    """간단한 주간 요약 생성기(룰 기반).

    - chats: [{'date': 'YYYY-MM-DD', 'role': 'user'|'assistant', 'text': '...'}, ...]
    - 반환값: summary JSON(사전 형태)
    """
    # LLM을 사용해 요약 생성 (실패 시 룰 기반 폴백)
    texts = [c.get("text", "") for c in chats]
    combined = "\n".join(texts).strip()
    summary_text = ""
    key_traits: list = []
    events: list = []
    profile_updates: dict = {}

    if combined:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "너는 간결한 주간 요약 생성기야. 주어진 대화 기록을 보고 2-3문장으로 핵심을 요약하고, 주요 특성(key traits)과 주요 사건(events)을 JSON으로 반환해. 출력은 JSON 형식이어야 한다."),
                ("user", "대화 기록:\n{chats}\n\n응답 형식(JSON): {\"summary\": str, \"key_traits\": list, \"events\": list, \"profile_updates\": dict}")
            ])
            llm = get_llm(temperature=0.0)
            chain = prompt | llm | StrOutputParser()
            out = chain.invoke({"chats": combined})
            # LLM이 JSON을 반환했을 가능성에 대비해 파싱 시도
            try:
                import json as _json

                parsed = _json.loads(out)
                summary_text = parsed.get("summary", "")[:max_chars]
                key_traits = parsed.get("key_traits", []) or []
                events = parsed.get("events", []) or []
                profile_updates = parsed.get("profile_updates", {}) or {}
            except Exception:
                # 폴백: 텍스트 앞부분 사용
                summary_text = out.strip()[:max_chars]
        except Exception:
            # LLM 실패 시 간단 폴백
            summary_text = combined[:max_chars]

    result = {
        "summary": summary_text,
        "key_traits": key_traits,
        "events": events,
        "profile_updates": profile_updates,
    }

    # DB에 저장(업서트)
    try:
        persona_repo.upsert_persona_summary(session_id=session_id, week_start=week_start, week_end=week_start, summary=summary_text)
    except Exception:
        # 실패해도 상위 로직이 처리
        pass
    return result


@lru_cache(maxsize=128)
def get_or_build_history_block(session_id: str, target_date: str, recent_days: int = 7) -> Dict[str, Any]:
    """history_block을 반환: 캐시 기반으로 동작. 데코레이터로 TTL이 적용됩니다.

    구현 주의사항은 기존과 동일합니다:
    - recent_chats: 실제 데이터는 chat_repo에서 불러오도록 향후 연결 필요
    - weekly_summaries: persona_repo에서 해당 주 요약을 조회하고, 없으면 summarize_week_tool 호출
    """
    # 실제 recent chats를 chat_repo에서 불러옵니다
    try:
        chat_repo = get_chat_repo()
        msgs = chat_repo.get_session_messages(session_id)
        # ChatLog -> dict 형식으로 변환
        recent_chats = [
            {"date": (m.created_at or "")[:10], "role": m.role, "text": m.text, "created_at": m.created_at}
            for m in msgs
        ]
    except Exception:
        # 실패 시 빈 리스트로 폴백
        recent_chats = []

    # 주간 요약 조회(예: target_date의 주를 week_start로 가정)
    week_start = target_date  # 간단 가정; 실제는 날짜->week_start 계산 필요
    summary_row = persona_repo.get_persona_summary(session_id, week_start)
    weekly_summaries = []
    if summary_row:
        weekly_summaries.append({"week_start": week_start, "summary": summary_row.get("summary")})
    else:
        # 빈 채팅이면 룰 기반 요약은 빈 문자열로 저장
        summary = summarize_week_tool(session_id, week_start, recent_chats)
        weekly_summaries.append({"week_start": week_start, "summary": summary.get("summary")})

    history_block = {
        "recent_chats": recent_chats,
        "weekly_summaries": weekly_summaries,
        "persona": persona_repo.get_latest_child_persona(session_id),
    }

    return history_block


__all__ = ["summarize_week_tool", "get_or_build_history_block"]
