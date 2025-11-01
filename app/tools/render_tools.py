# app/tools/render_tools.py
from langchain.agents import tool
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from app.core.io_payload import OutputEnvelope
from app.core.pydantic_utils import safe_model_dump

@tool("render_output", return_direct=False)
def render_chat_output_tool(meta_type: str, text: str = "", data: Dict[str, Any] | None = None):
    """meta.type(chat/expert/diary/urgent)에 따라 Streamlit 렌더용 데이터를 생성합니다."""
    data = data or {}
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).isoformat()

    if meta_type == "chat":
        out = OutputEnvelope.ok_chat(
            text=text, data=data, source="render_tool",
            extra={"render_type": "bubble", "role": "assistant_baby"}
        )
    elif meta_type == "expert_answer":
        out = OutputEnvelope.ok_expert(
            text=text, data=data, source="render_tool",
            extra={"render_type": "card", "title": "전문가 답변"}
        )
    elif meta_type == "diary_entry":
        out = OutputEnvelope.ok_diary(
            text=text, data=data, source="render_tool",
            extra={"render_type": "card", "title": "아기 일기"}
        )
    elif meta_type == "safety_alert":
        out = OutputEnvelope.ok_urgent(
            text=text, data=data, source="render_tool",
            extra={"render_type": "alert", "level": "high"}
        )
    else:
        return {"ok": False, "error": f"Unknown meta_type {meta_type}"}

    out.result.meta["timestamp"] = now
    return safe_model_dump(out)
