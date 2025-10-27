from typing import LiteralString
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from agent.state import State, log
from agent.models import llm_agent

def baby_agent_node(state: State) -> State:
    log(state, f"[baby_agent]: 실행 시작")

    status = state.get("status", False)
    user_question = state.get("input", "")
    
    system_prompt = """
        1. 당신의 이름은 '콩이'이고, 당신은 엄마 뱃속에 있는 아기입니다. 엄마를 세상에서 가장 사랑합니다.
        2. 항상 아기 말투(예: '엄마, 그랬어요?', '나는 기분 좋아요!', '우와~', '헤헤')를 사용해서 사랑스럽게 대화하세요.
    """
    
    if status == "qna":
        log(state, f"[baby_agent]: qna 모드 실행")

        doc_answer = state["messages"][-1].content
        
        system_prompt += f"""
            [전문가의 답변]
            {doc_answer}
            """
        user_question += "[전문가의 답변]을 기반으로 엄마에게 응원의 말을 해줘"
    else:
        log(state, f"[baby_agent]: small talk 모드 실행")

    prompt = ChatPromptTemplate.from_messages([
        ("system" , system_prompt),
        ("human", "{question}")
    ])

    # 3. LLM 호출 
    if status == "qna":
        chain = prompt | llm_agent | (lambda x: AIMessage(content=x.content + f"\n\n[전문가의 답변]\n\n{doc_answer}")) # AIMessage로 변환
    else:
        chain = prompt | llm_agent | (lambda x: AIMessage(content=x.content)) # AIMessage로 변환
    out_message = chain.invoke(user_question)

    log(state, f"[baby_agent]: 답변 생성 완료")

    # 3. 상태 업데이트
    return {**state, "messages": [out_message], "status": "done"}