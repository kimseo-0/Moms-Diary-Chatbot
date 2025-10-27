from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
import os
from typing import Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.state import State, log
from agent.models import llm_agent
from src.infra.db.baby_db import upsert_baby_profile, DEFAULT_DB_PATH, init_baby_db

class BabyProfile(BaseModel):
    """사용자 대화에서 추출할 수 있는 아기/산모의 프로필 정보"""
    nickname: Optional[str] = Field(None, description="아기의 태명")
    sex: Optional[Literal['남자', '여자', '모름']] = Field(None, description="아기의 성별")
    lmp_date: Optional[str] = Field(None, description="마지막 월경 시작일 (YYYY-MM-DD 형식으로 변환)")
    due_date: Optional[str] = Field(None, description="출산 예정일 (YYYY-MM-DD 형식으로 변환)")
    notes: Optional[str] = Field(None, description="기타 중요한 메모 (알레르기, 중요한 날짜 등)")

parser = JsonOutputParser(pydantic_object=BabyProfile)

if not os.path.exists(DEFAULT_DB_PATH):
    init_baby_db()

db_system_prompt = (
    "당신은 사용자의 대화에서 아기 및 산모에 대한 중요한 프로필 정보를 추출하는 전문 데이터 추출기입니다. "
    "정보 추출에 성공하면 다음 JSON 스키마를 엄격하게 준수하여 출력해야 합니다. "
    "정보가 추출되지 않으면 반드시 모든 필드를 null/None으로 출력해야 합니다. "
    "날짜는 반드시 YYYY-MM-DD 형식으로 변환해야 합니다.\n\n"
    "JSON Schema:\n{schema}"
)

def persona_agent_node(state: State) -> dict:
    log(state, "[persona_agent_node]: 병렬 정보 추출 시작")
    
    current_messages = state["messages"]
    session_id = state["session_id"]
    
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", db_system_prompt),
        ("user", "이전 대화 내용을 바탕으로 프로필 정보를 추출하세요. [이전 대화 내용]{messages}")
    ]).partial(schema=parser.get_format_instructions())

    extraction_chain = extraction_prompt | llm_agent | parser
    
    try:
        extracted_data: Dict[str, Any] = extraction_chain.invoke({"messages": current_messages})
        data_to_save = {k: v for k, v in extracted_data.items() if v is not None and v != ""}
        
        db_result_msg = "추출할 정보 없음."
        if data_to_save:
            upsert_baby_profile(session_id=session_id, data=data_to_save, db_path=DEFAULT_DB_PATH)
            saved_items = ", ".join(data_to_save.keys())
            db_result_msg = f"성공적으로 {saved_items} 정보를 DB에 저장했습니다."

        log(state, f"[persona_agent_node]: DB 결과: {db_result_msg[:50]}...")
        
    except Exception as e:
        db_result_msg = f"데이터 추출/저장 중 오류 발생: {e}"
        log(state, f"[persona_agent_node]: 오류: {e}")

    # 4. 상태 업데이트 (DB 결과 저장 및 다음 노드로 흐름 전달)
    return {"db_result": db_result_msg}