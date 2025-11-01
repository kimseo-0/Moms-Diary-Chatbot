from __future__ import annotations
from typing import Any, Dict, Literal, Optional, TypedDict
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator

# ====== 공통 타입 ======
InputType = Literal["chat", "expert", "diary", "urgent"]
OutputType = Literal["chat", "expert_answer", "diary_entry", "safety_alert"]

ISO8601 = "%Y-%m-%dT%H:%M:%S%z"


class InputMetadata(BaseModel):
    """사용자 입력에 동봉되는 메타데이터 (의도 추정/라우팅 힌트)"""
    type: InputType = Field(..., description="사용자 의도 힌트")
    source: str = Field(default="ui", description="입력 소스 (ui|api|test...)")
    date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    week: Optional[int] = Field(default=None, description="임신 주차 (정수)")
    language: str = Field(default="ko", description="입력 언어 코드")
    extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("date")
    @classmethod
    def _validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # YYYY-MM-DD 간단 검증
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except Exception:
            raise ValueError("date must be 'YYYY-MM-DD'")
        return v


class InputPayload(BaseModel):
    """사용자 입력의 본문(payload)"""
    text: str = Field(..., description="사용자 입력 텍스트")
    context: Optional[str] = Field(default=None, description="대화/세션 컨텍스트(선택)")
    metadata: InputMetadata


class InputEnvelope(BaseModel):
    """서버가 받는 최상위 입력 오브젝트"""
    session_id: str = Field(..., description="엄마(사용자) 고유 식별자")
    payload: InputPayload


# ====== 출력(Result) ======
class ResultMeta(BaseModel):
    """출력 렌더링 및 추적용 메타정보"""
    source: str = Field(default="agent", description="응답 생성 소스(노드/툴 등)")
    type: OutputType = Field(..., description="렌더 타입 매핑 키")
    # timestamp: str = Field(default_factory=lambda: datetime.now(timezone('Asia/Seoul')))
    extra: Dict[str, Any] = Field(default_factory=dict)


class Result(BaseModel):
    """어시스턴트가 그리는 최종 데이터 컨테이너"""
    text: str = Field(..., description="대화 버블에 표시될 텍스트(또는 카드의 주요 텍스트)")
    data: Dict[str, Any] = Field(default_factory=dict, description="카드 데이터(전문가/일기/긴급)")
    meta: ResultMeta


class OutputEnvelope(BaseModel):
    """서버가 반환하는 최상위 출력 오브젝트"""
    ok: bool = True
    result: Optional[Result] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def ok_chat(cls, text: str, *, extra: Optional[Dict[str, Any]] = None, source: str = "agent") -> "OutputEnvelope":
        return cls(
            ok=True,
            result=Result(
                text=text,
                data={},
                meta=ResultMeta(source=source, type="chat", extra=extra or {}),
            ),
        )

    @classmethod
    def ok_expert(cls, text: str, data: Dict[str, Any], *, extra: Optional[Dict[str, Any]] = None,
                  source: str = "medical_qna_node") -> "OutputEnvelope":
        return cls(
            ok=True,
            result=Result(
                text=text,
                data=data,
                meta=ResultMeta(source=source, type="expert_answer", extra=extra or {}),
            ),
        )

    @classmethod
    def ok_diary(cls, text: str, data: Dict[str, Any], *, extra: Optional[Dict[str, Any]] = None,
                 source: str = "generate_diary_node") -> "OutputEnvelope":
        return cls(
            ok=True,
            result=Result(
                text=text,
                data=data,
                meta=ResultMeta(source=source, type="diary_entry", extra=extra or {}),
            ),
        )

    @classmethod
    def ok_urgent(cls, text: str, data: Dict[str, Any], *, extra: Optional[Dict[str, Any]] = None,
                  source: str = "urgent_triage_node") -> "OutputEnvelope":
        return cls(
            ok=True,
            result=Result(
                text=text,
                data=data,
                meta=ResultMeta(source=source, type="safety_alert", extra=extra or {}),
            ),
        )

    @classmethod
    def err(cls, code: str, message: str, *, retryable: bool = False) -> "OutputEnvelope":
        return cls(ok=False, error={"code": code, "message": message, "retryable": retryable})
