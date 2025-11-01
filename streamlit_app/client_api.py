# streamlit_app/client_api.py
from __future__ import annotations
import os
import requests
from typing import Dict, Any

API_BASE = os.getenv("MOMS_API_BASE", "http://localhost:8000")

def post_chat(session_id: str, text: str, *, week: int = 22, date: str | None = None, context: str | None = None) -> Dict[str, Any]:
    """
    서버의 /api/chat 엔드포인트 호출.
    metadata.type은 형식상 'chat'으로 넣지만, 실제 intent/plan은 서버 플래너가 재판단.
    """
    payload = {
        "session_id": session_id,
        "payload": {
            "text": text,
            "context": context,
            "metadata": {
                "type": "chat",
                "source": "streamlit",
                "date": date,
                "week": week,
                "language": "ko",
                "extra": {},
            },
        },
    }
    url = f"{API_BASE}/api/chat"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_diary(session_id: str, date: str) -> Dict[str, Any]:
    url = f"{API_BASE}/api/diary/{session_id}/{date}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def get_chat_history(session_id: str) -> Dict[str, Any]:
    url = f"{API_BASE}/api/chat/{session_id}/history"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def get_chat_history_by_date(session_id: str, date: str) -> Dict[str, Any]:
    url = f"{API_BASE}/api/chat/{session_id}/history/{date}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def init_profile(session_id: str) -> Dict[str, Any]:
    url = f"{API_BASE}/api/profile/init/{session_id}"
    r = requests.post(url, timeout=10)
    r.raise_for_status()
    return r.json()


def save_diary(session_id: str, date: str, content: str) -> Dict[str, Any]:
    url = f"{API_BASE}/api/diary"
    payload = {"session_id": session_id, "date": date, "content": content}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()
