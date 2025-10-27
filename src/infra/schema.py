from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any

# class BabyProfile(BaseModel):
#     """사용자 대화에서 추출할 수 있는 아기/산모의 프로필 정보"""
#     nickname: Optional[str] = Field(None, description="아기의 태명")
#     sex: Optional[Literal['남자', '여자', '모름']] = Field(None, description="아기의 성별")
#     lmp_date: Optional[str] = Field(None, description="마지막 월경 시작일 (YYYY-MM-DD 형식으로 변환)")
#     due_date: Optional[str] = Field(None, description="출산 예정일 (YYYY-MM-DD 형식으로 변환)")
#     notes: Optional[str] = Field(None, description="기타 중요한 메모 (알레르기, 중요한 날짜 등)")

class ChatSchema(BaseModel):
    """채팅 결과 스키마"""
    baby_answer: str
    doctor_answer: str