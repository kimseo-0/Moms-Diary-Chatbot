from typing import Iterator, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.agent.graph import compiled_graph
from src.infra.db.chat_db import load_messages, save_message 

def _prepare_initial_state(session_id: str, question: str) -> Dict[str, Any]:
    """DB의 대화 기록을 LangGraph의 초기 State 포맷으로 변환합니다."""
    
    # 1. DB에서 대화 기록 로드
    db_history = load_messages(session_id)

    history = []
    
    # 2. LangChain Message 객체로 변환 (AIMessage, HumanMessage)
    for chat in db_history:
        if chat['role'] == 'user':
            history.append(HumanMessage(content=chat['content']))
        elif chat['role'] == 'assistant':
            history.append(AIMessage(content=chat['content']))

    # 3. 현재 사용자 질문 추가
    history.append(HumanMessage(content=question))

    # 4. LangGraph의 초기 State 생성
    return {
        "input": question,
        "messages": history,
        "session_id": session_id
    }


def stream_chat(session_id: str, question: str) -> Iterator[str]:
    """
    LangGraph를 실행하고 응답을 스트리밍하며, 최종 결과를 DB에 저장합니다.
    """
    # 1. 초기 상태 준비 및 사용자 메시지 DB 저장
    initial_state = _prepare_initial_state(session_id, question)
    save_message(session_id, "user", question) 

    final_answer = ""
    
    # 2. LangGraph 스트림 실행
    for chunk in compiled_graph.stream(initial_state, stream_mode="values"):
        
        # 3. LangGraph의 'messages' 상태에서 최종 AI 응답 추출
        if "messages" in chunk and chunk["messages"][-1].type == "ai":
            new_content = chunk["messages"][-1].content
            
            # 4. 이전 내용과 비교하여 새로 생성된 토큰만 yield (스트리밍)
            if new_content and len(new_content) > len(final_answer):
                yield new_content[len(final_answer):] 
                final_answer = new_content

    # 5. 최종 어시스턴트 메시지 DB 저장 (스트림 완료 후)
    if final_answer:
        save_message(session_id, "assistant", final_answer)

def send_chat(session_id: str, question: str) -> str:
    initial_state = _prepare_initial_state(session_id, question)
    save_message(session_id, "user", question) 

    final_answer = compiled_graph.invoke(initial_state)
    
    if final_answer:
        save_message(session_id, "assistant", final_answer["messages"][-1].content)
    pass

    return final_answer["messages"][-1].content

if __name__ == "__main__":
    result = send_chat("user-123", "안녕 너의 이름은 튼튼이고, 여자 아이야. 오늘 기분은 어때?")

    print(result)