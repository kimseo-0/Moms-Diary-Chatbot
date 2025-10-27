from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.state import State, log
from agent.models import llm_agent
from agent.rag_tools import format_docs


system_prompt = (
    "너는 산부인과 경력 30년 이상의 전문의야. 산모의 질문에 대해 전문적이고 명확하게 대답해."
    "답변은 항상 신뢰감을 주는 어조로 작성해야 해."
    """
    산모의 궁금한 점을 주어진 컨텍스트를 근거로 정확하게 대답해

     [작성 규칙]
     - 컨텍스트에 없으면 문서에 "근거 없음" 이라고 말해라
     - 한글로 대답하라
     
     [출처 작성 규칙]
     - 출처 내용을 있는 그대로 작성할 것
     - 있는 그대로 작성 할 것
     - 여러 문서를 근거하고 있을 경우 누락 없이 모두 작성하라

     [컨텍스트]
     {context}
    """
    ) 

rag_prompt = ChatPromptTemplate.from_messages([
    ("system" , system_prompt),
    ("human", "{question}")
])

rag_chain = rag_prompt | llm_agent | (lambda x: AIMessage(content=x.content)) # AIMessage로 변환

def doctor_agent_node(state: State) -> State:
    user_question = state["messages"][-1].content
    documents = state["documents"]
    
    log(state, f"[doctor_agent]: RAG 검색 시작. 질문: {user_question[:20]}...")

    docs_txt = format_docs(documents)
    out_message = rag_chain.invoke({"context": docs_txt, "question": user_question})
    
    log(state, f"[doctor_agent]: RAG 기반 답변 완료")

    # LangGraph 노드는 상태 업데이트를 위한 딕셔너리를 반환합니다.
    return {**state, "messages": [out_message], "status" : "qna"}