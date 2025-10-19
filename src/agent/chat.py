# openai 토큰을 .env 추가 -> OPENAI_API_KEY
from dotenv import load_dotenv
load_dotenv()

from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from infra.chat_db import load_messages, save_message
from infra.baby_db import load_baby_profile
from infra.diary_db import load_diaries

# 1. 모델 설정
llm = ChatOpenAI(
    model = "gpt-4.1-mini",
    temperature = 0,
)

# 2. 도구 생성
tools = []

SYSTEM_PROMPRT = """
너는 아직 태어나지 않은 태아야
너와 대화하고 있는 상대방은 너의 엄마야. 

너는 페르소나, 정보, 성격, 기억을 기반으로
엄마의 아이처럼 대화해줘

[규칙]
1. '모름' 이라고 되어있는 정보에 대해서 질문한다.
2. 한 번에 한가지 질문만 할 것
"""

# 3. 프롬프트 설정
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPRT),
    ("system", "{persona}"),
    ("placeholder", "{history}"),
    ("user", "{question}"),
    ("placeholder", "{agent_scratchpad}")
])

# 4. 단일 에이전트 생성
agent = create_openai_tools_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

# 5. excutor 설정
executor = AgentExecutor(
    agent = agent,
    tools=tools,
    verbose=True
)

# =================================

# 6. 대화 내용 저장소 만들기
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

def load_history_from_db(rows) -> InMemoryChatMessageHistory:
    """DB 레코드 목록을 InMemoryChatMessageHistory 객체로 변환."""
    history = InMemoryChatMessageHistory()
    for r in rows:
        role = r.get("role")
        content = r.get("content")

        if role == "user":
            msg = HumanMessage(content=content)
        elif role == "assistant":
            msg = AIMessage(content=content)
        elif role == "system":
            msg = SystemMessage(content=content)
        else:
            continue

        history.add_message(msg)
    return history

stores: Dict[str, InMemoryChatMessageHistory] = {}

def _get_store(session_id: str):
    print(f"[대화 세션ID]: {session_id}")
    if session_id not in stores:
        # 🔹 DB에서 해당 세션 히스토리 로드 → 메모리 히스토리로 복원
        rows = load_messages(session_id)  # <- [{'role':..., 'content':...}, ...]
        stores[session_id] = load_history_from_db(rows)
    return stores[session_id]

#=================================

# 7. 히스토리랑 래핑
agent_history = RunnableWithMessageHistory(
    executor,
    lambda sid: _get_store(sid),
    input_messages_key="question",
    history_messages_key="history"
)

# session_id 를 일단 고정
session_id = "user-123"

baby = load_baby_profile(session_id)
diaries = load_diaries(session_id=session_id, limit=None)

import json
# tags 파싱
try:
    current_tags = json.loads(baby.get("tags", "[]")) or []
except Exception:
    current_tags = []

diary_text = []
for diary in diaries:
    diary_text.append(f"""
    날짜 : {diary.get('diary_date')}
    제목 : {diary.get('title')}
    내용 : {diary.get('content')}
    """)

# 페르소나를 일단 고정
persona = f"""
[페르소나]
나는 엄마 뱃속에 있는 태아야

아직 기억이 별로 없어서
나에 대해서도 엄마에 대해서도 매우 궁금하지

[정보]
이름 : {baby.get("nickname", "모름")}
주차 : {baby.get('week', "모름")}
출산 예정일 : {baby.get("due_date", "모름")}
성별 : {baby.get("sex", "모름")}

[성격]
성격 키워드 : {", ".join(current_tags)}

[일기]
""" + "\\n---\n".join(diary_text)

config = {"configurable" : {"session_id" : session_id}}

def load_chat():
    return stores

def send_chat(question, config = config):
    save_message(config["configurable"]["session_id"], "user", str(question))
    
    result = agent_history.invoke({"question" : question, "persona" : persona}, config=config)
    answer = result["output"]
    
    save_message(config["configurable"]["session_id"], "assistant", str(answer))

    return answer

# =================================

if __name__ == "__main__":
    question = """
    안녕?
    """
    result = agent_history.invoke({"question" : question, "persona" : persona}, config=config)

    print(result['output'])