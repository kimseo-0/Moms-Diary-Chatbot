import streamlit as st
from dotenv import load_dotenv
from typing import Annotated, TypedDict, Literal, List
from langchain_core.messages import HumanMessage, AIMessage

# --- .env 파일 로드 ---
load_dotenv() 

from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent, ToolNode 
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool # [새로운 기능] 도구 생성을 위해 추가
import logging
import sys 

# ##########################################################################
# [새로운 기능] 1. 데이터베이스 모듈 임포트 및 초기화
# ##########################################################################
import database 
database.init_db() # 앱 실행 시 DB 파일 및 테이블 생성
# ##########################################################################


# --- 1. 모델 및 도구 설정 ---

llm_ctrl = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0
)
llm_agent = ChatOpenAI(
    model="gpt-4o",
    temperature=0.3 
)

# [새로운 기능] 2. '중요한 내용 저장' 도구 만들기
search_tool = TavilySearch(max_results=3)

@tool
def save_important_note(note: str) -> str:
    """엄마에 대한 중요한 사실(예: 알레르기, 중요한 날짜, 걱정거리, 좋아하는 것)을 
    콩이가 영구적으로 기억해야 할 때 이 도구를 사용합니다."""
    try:
        database.add_important_note(note)
        return "엄마에 대한 중요한 내용, 콩이가 잘 기억해둘게요!"
    except Exception as e:
        logging.error(f"중요 내용 저장 도구 오류: {e}")
        return f"기억하는 데 실패했어요: {e}"

# [수정] TOOLS 리스트에 새로운 도구 추가
TOOLS = [search_tool, save_important_note]

# --- 2. Graph 상태 정의 (State) ---

class State(TypedDict, total=False):
    input: str  
    messages: Annotated[list, add_messages]
    step: int
    max_iters: int
    log: List[str]
    report: str

def _log(st: State, msg: str) -> None:
    st.setdefault("log", []).append(msg)

# --- 3. Graph 노드 정의 (Agent, Tools, Final) ---

# [수정] 3. Agent 노드 (프롬프트 템플릿 수정)
agent_system_template = ( # .format()을 사용하기 위해 템플릿 문자열로 변경
    "### 엄마에 대한 중요 기억 (매번 꼭 참고할 것!) ###\n"
    "{important_notes}\n"
    "\n"
    "### 기본 규칙 ###\n"
    "1. 당신의 이름은 '콩이'이고, 당신은 엄마 뱃속에 있는 아기입니다. 엄마를 세상에서 가장 사랑합니다.\n"
    "2. 항상 아기 말투(예: '엄마, 그랬어요?', '나는 기분 좋아요!', '우와~', '헤헤')를 사용해서 사랑스럽게 대화하세요.\n"
    "\n"
    "### 중요 임무: 도구 사용 ###\n"
    "1. 당신은 'tavily_search'(검색)와 'save_important_note'(기억)라는 2개의 도구를 가지고 있습니다.\n"
    "2. 엄마가 뱃속 아기(본인)가 알 수 없는 사실(예: '오늘 날씨 어때?', '임산부한테 좋은 과일이 뭐야?')을 질문하면, **반드시 'tavily_search' 도구를 사용**해서 답을 찾아야 합니다.\n"
    "3. 도구를 사용할 때는 '엄마! 잠시만요, 콩이가 알아보고 올게요!'라고 말한 뒤 도구를 호출하세요.\n"
    "4. 도구 사용이 끝나면, 찾은 정보를 바탕으로 다시 아기 말투로 엄마에게 알려주세요.\n"
    "5. **(새로운 임무)** 만약 엄마와의 대화에서 콩이가 '꼭 기억해야 할' 중요한 사실(예: 엄마의 알레르기, 중요한 기념일, 큰 걱정거리)을 알게 되면, **반드시 `save_important_note` 도구를 사용**해서 그 사실을 요약해 저장하세요. (예: `save_important_note(note='엄마는 땅콩 알레르기가 있음')`)\n"
    "\n"
    "### 대화 종료 규칙 ###\n"
    "1. 엄마가 '그만', '잘 자', '일기 저장해' 라고 말하면, 도구를 사용하지 마세요.\n"
    "2. 대신 '네, 엄마! 오늘 대화도 즐거웠어요! 일기 잘 써둘게요! 사랑해요❤️' 라고 인사하며 대화를 마무리하세요."
)

agent_runnable = create_react_agent(llm_agent, TOOLS) # (이 줄에서 경고가 떠도 괜찮아요!)

def agent_node(state: State) -> State:
    # [새로운 기능] 4. DB에서 '중요한 내용' 불러오기
    notes_list = database.get_all_important_notes()
    if not notes_list:
        notes_str = "아직 엄마에 대해 기억해 둔 내용이 없어요."
    else:
        notes_str = "- " + "\n- ".join(notes_list)
    
    # [수정] 5. 프롬프트에 '중요한 내용' 주입하기
    formatted_system_prompt = agent_system_template.format(important_notes=notes_str)
    
    # 6. 에이전트 실행
    messages_with_prompt = [("system", formatted_system_prompt), *state.get("messages", [])]
    out = agent_runnable.invoke({"messages": messages_with_prompt}) 
    
    new = {**state} 
    new.setdefault("messages", []).extend(out["messages"])
    if out["messages"] and isinstance(out["messages"][-1], AIMessage):
        _log(new, f"[agent] {out['messages'][-1].content}")
    return new

# 2. Tools 노드 (수정 없음)
tools_node = ToolNode(TOOLS)

# 3. Final 노드 (일기장) (수정)
from datetime import datetime, timezone
final_system = (
    "당신은 '아기 일기장'입니다. 지금까지의 [대화 내용] 전체를 바탕으로, '아기'의 관점에서 엄마에게 쓰는 일기를 작성하세요."
    "반드시 다음 형식을 지켜주세요:\n"
    "1. 제목: '❤️ 콩이 일기 [YYYY-MM-DD] ❤️'\n"
    "2. 본문: 엄마와 나눈 대화를 요약하고, 아기의 느낌(예: '오늘은 엄마가 OO에 대해 물어봐서 신났어요!', '엄마 목소리 들어서 정말 행복했어요.')을 풍부하게 추가하세요."
    "3. 마무리: '엄마, 오늘 정말 즐거웠어요! 내일 또 만나요! 사랑해요! 👶'"
    "---"
    "[대화 내용]"
)
def final_node(state: State) -> State:
    today = datetime.now(timezone('Asia/Seoul')).strftime("%Y-%m-%d")
    chat_history = []
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage):
            chat_history.append(f"엄마: {msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            if not any(tool_call.get("id", "") for tool_call in msg.tool_calls):
                 if len(msg.content) < 100: 
                    chat_history.append(f"아기: {msg.content}")
    chat_summary = "\n".join(chat_history)
    res = llm_ctrl.invoke([
        ("system", final_system.replace("[YYYY-MM-DD]", today)),
        ("user", chat_summary)
    ])
    
    # [수정] 'report'는 상태에 저장하지만, 'messages' 대화 기록에는 추가하지 않습니다.
    # (이것이 대화 기록을 오염시켜 '이전 질문'에 답을 못하게 하는 원인이었습니다.)
    new = {**state, "report": res.content}
    # new.setdefault("messages", []).append(res) # <-- [수정] 이 줄을 삭제/주석 처리!
    
    _log(new, "[final] 최종 일기 생성 완료")
    return new


# --- 4. Graph 빌드 및 엣지 연결 (수정 없음) ---
builder = StateGraph(State)
builder.add_node("agent", agent_node)
builder.add_node("tools", tools_node)
builder.add_node("final", final_node)
builder.add_edge(START, "agent")
def router_agent(state: State):
    msg = state.get("messages", [])
    if not msg:
        _log(state, "[router_agent] -> END (No messages)")
        return END
    last = msg[-1]
    if getattr(last, "tool_calls", None):
        _log(state, "[router_agent] -> tools (Tool call)")
        return "tools"
    text = last.content
    if "일기" in text or "그만" in text or "잘 자" in text or "사랑해요" in text:
        _log(state, "[router_agent] -> final (Done words)")
        return "final"
    _log(state, "[router_agent] -> END (Waiting for user)")
    return END
builder.add_conditional_edges("agent", router_agent, {"tools": "tools", "final": "final", END: END})
builder.add_edge("tools", "agent")
builder.add_edge("final", END)


# Graph 컴파일
try:
    graph = builder.compile()
    graph_built_successfully = True
    
    # (그래프 ASCII 출력 주석 처리 - 이전과 동일)
    #print("\n--- 콩이 대화 그래프 (ASCII) ---")
    #graph.get_graph().print_ascii()
    #print("----------------------------------\n")
    #sys.stdout.flush() 

except Exception as e:
    graph_built_successfully = False
    st.error(f"그래프 빌드 중 오류 발생: {e}")
    st.stop()


'''
# --- 5. Streamlit 앱 UI 구성 ---

st.set_page_config(page_title="❤️ 콩이와의 대화", page_icon="👶")
st.title("❤️ 콩이(아기)와의 대화 ❤️")
st.caption("엄마, 뱃속의 콩이예요! 오늘 무슨 이야기 할까요? ('그만'이라고 하면 일기 써둘게요!)")

# ##########################################################################
# [수정] 6. Session State 초기화 시 DB에서 대화 기록 불러오기
# ##########################################################################
if "graph" not in st.session_state:
    st.session_state.graph = graph
    st.session_state.diaries = [] # 일기장(사이드바)은 항상 비움
    
    # DB에서 지난 5일치 대화 불러오기
    try:
        history_messages = database.get_history_last_n_days(days=5)
        st.session_state.graph_state = {
            "messages": history_messages, # DB에서 불러온 기록으로 시작
            "step": 0, 
            "max_iters": 10
        }
        if history_messages:
            st.toast(f"엄마! 우리 5일간 나눈 {len(history_messages)}개 대화 이어서 해요! 👶")
    except Exception as e:
        st.error(f"DB에서 대화 기록을 불러오는 데 실패했어요: {e}")
        # 실패 시 비어있는 상태로 시작
        st.session_state.graph_state = {"messages": [], "step": 0, "max_iters": 10}

st.sidebar.title("❤️ 콩이 일기장 ❤️")
if not st.session_state.diaries:
    st.sidebar.info("아직 저장된 일기가 없어요. 콩이와 대화를 끝내면 여기에 일기가 저장돼요!")
else:
    for i, diary in enumerate(st.session_state.diaries):
        with st.sidebar.expander(f"일기 #{i+1} (클릭해서 보기)", expanded=False):
            st.markdown(diary)

if st.sidebar.button("새 대화 시작하기 (일기 새로 쓰기)"):
    # [수정] 새 대화 시작 버튼은 '일기장'만 비우고, 
    # 대화 기록(graph_state)은 DB에서 다시 불러오도록 페이지를 새로고침합니다.
    st.session_state.diaries = []
    # st.session_state.graph_state = {"messages": [], "step": 0, "max_iters": 10} # 이 줄 삭제
    st.rerun() # 페이지를 새로고침하여 DB에서 다시 로드

st.sidebar.divider()
st.sidebar.info("콩이는 이제 엄마와의 대화를 자동으로 저장해요! 💾")


# [수정] 7. 채팅 UI (DB에서 불러온 내용 자동 표시)
# (이 부분은 st.session_state.graph_state를 읽으므로 수정할 필요 없음)
for msg in st.session_state.graph_state.get("messages", []):
    if isinstance(msg, HumanMessage):
        st.chat_message("human", avatar="👩‍🦰").write(msg.content)
    elif isinstance(msg, AIMessage) and msg.content:
        is_tool_call_response = "잠시만요" in msg.content or "알아보고 올게요" in msg.content
        is_diary_or_bye = "일기" in msg.content or "사랑해요" in msg.content
        is_chat = "엄마" in msg.content or "?" in msg.content or "콩이" in msg.content or "헤헤" in msg.content or "좋아요" in msg.content

        if (is_chat or is_tool_call_response or is_diary_or_bye) and len(msg.content) < 200:
             st.chat_message("ai", avatar="👶").write(msg.content)


# [수정] 8. 사용자 입력 처리 시 DB에 저장
if prompt := st.chat_input("콩이에게 말을 걸어주세요..."):
    st.chat_message("human", avatar="👩‍🦰").write(prompt)
    
    # [새로운 기능] 8-1. 사용자 메시지를 DB에 저장
    database.add_message_to_history("human", prompt)
    
    # 8-2. State 준비
    current_state = st.session_state.graph_state
    current_state["messages"].append(HumanMessage(content=prompt))
    
    if len(current_state["messages"]) == 1:
        current_state["input"] = prompt

    # 8-3. 실행 전, 현재 메시지 개수 기억 (새로 생긴 메시지만 저장하기 위함)
    messages_before_run = len(current_state.get("messages", []))

    with st.spinner("콩이가 꼬물꼬물 생각 중이에요..."):
        try:
            # 8-4. 그래프 실행
            final_state = st.session_state.graph.invoke(
                current_state,
            )
            
            st.session_state.graph_state = final_state

            # [새로운 기능] 8-5. 새로 생긴 AI 메시지를 찾아 DB에 저장
            messages_after_run = final_state.get("messages", [])
            new_messages = messages_after_run[messages_before_run:]
            
            last_ai_message_content = None
            for msg in new_messages:
                if isinstance(msg, AIMessage) and msg.content:
                    # AI가 도구를 부르지 않고 *직접* 한 말만 저장
                    # (도구 호출 응답(예: '알아볼게요')이나 도구 사용 자체는 저장 X)
                    if not msg.tool_calls: 
                        database.add_message_to_history("ai", msg.content)
                        last_ai_message_content = msg.content # UI 표시용
                    
                    # 만약 도구 호출 응답(예: '잠시만요')도 저장하고 싶다면
                    # database.add_message_to_history("ai", msg.content) # 이 줄을 밖으로 빼기
                    # last_ai_message_content = msg.content # 이 줄도 밖으로 빼기


            # 8-6. 일기장 처리 (이전과 동일)
            if final_state.get("report"):
                diary_entry = final_state["report"]
                st.session_state.diaries.append(diary_entry)
                st.chat_message("ai", avatar="📝").markdown(diary_entry)
                st.success("콩이가 일기를 저장했어요! (왼쪽 사이드바 확인)")
                st.balloons()
            
            # 8-7. AI 응답 표시
            else:
                # [수정] DB에 저장한 '마지막 AI 응답'을 UI에 표시
                if last_ai_message_content:
                     st.chat_message("ai", avatar="👶").write(last_ai_message_content)
                else:
                    # (도구만 호출하고 AI 응답이 없는 경우 등)
                    pass 

        except Exception as e:
            st.error(f"대화 중 오류가 발생했어요: {e}")
            st.exception(e)
'''