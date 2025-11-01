# app/core/state.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from typing_extensions import TypedDict

from pydantic import BaseModel, Field
from app.core.io_payload import InputEnvelope, OutputEnvelope

class Task(TypedDict, total=False):
    name: str
    args: Dict[str, Any]

class AgentState(BaseModel):
    session_id: str
    input: InputEnvelope
    plan: List[Task] = Field(default_factory=list)
    final: Optional[OutputEnvelope] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
