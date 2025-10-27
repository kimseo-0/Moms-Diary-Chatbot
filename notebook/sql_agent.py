import streamlit as st
import sqlite3
import os
import datetime
from zoneinfo import ZoneInfo # 타임존 변환
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 최신 LangChain 임포트 경로
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit

# --- ✅ [수정됨] 캘린더 함수 임포트 ---
from streamlit_calendar import calendar 


# --- ✅ 환경 변수 로드 ---
load_dotenv()

# --- 1. 데이터베이스 설정 (이전과 동일) ---
DB_NAME = "diary.db"

def setup_database():
    """SQLite DB와 'diary' 테이블을 초기화합니다."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        content TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

# --- 2. LangChain SQL 에이전트 설정 (이전과 동일) ---
@st.cache_resource
def get_agent(api_key):
    """LangChain SQL 에이전트를 생성하고 반환합니다."""
    try:
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, api_key=api_key)
        db_uri = f"sqlite:///{DB_NAME}"
        db = SQLDatabase.from_uri(db_uri)
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        agent_executor = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            verbose=True, 
            agent_type="openai-tools"
        )
        return agent_executor
    except Exception as e:
        st.error(f"에이전트 로딩 중 오류 발생: {e}")
        st.stop()

# --- 3. 에이전트 시스템 프롬프트 (이전과 동일) ---
def get_system_prompt():
    """(일기 '작성'용) 에이전트에게 역할과 규칙을 부여하는 기본 프롬프트"""
    today_str = datetime.date.today().isoformat() 
    prompt = f"""
    당신은 'diary' 테이블을 관리하는 SQL 에이전트입니다.
    오늘 날짜는 {today_str}입니다.
    테이블 스키마: CREATE TABLE diary (id INTEGER, date TEXT UNIQUE, content TEXT)
    [규칙]
    1.  사용자의 요청을 분석하여 '날짜'와 '일기 내용'을 추출합니다.
    2.  '오늘' 또는 날짜 언급이 없으면 {today_str}을 날짜로 사용합니다.
    3.  '어제'는 { (datetime.date.today() - datetime.timedelta(days=1)).isoformat() } 입니다.
    4.  [가장 중요] 일기 저장 및 추가:
        -   반드시 `INSERT ... ON CONFLICT (date) DO UPDATE SET content = content || ' ' || excluded.content` 쿼리를 사용해야 합니다.
    5.  [금지] `INSERT OR REPLACE`는 절대 사용하지 마세요.
    6.  일기를 조회(SELECT)할 수도 있습니다.
    7.  모든 작업 완료 후, 사용자에게 한국어로 "저장했습니다." 또는 "추가했습니다." 등 친절하게 작업 결과를 보고해야 합니다.
    """
    return prompt

# --- (새 함수) 달력 조회용 DB 함수 (이전과 동일) ---
def get_diary_entry(selected_date):
    """선택된 날짜의 일기를 DB에서 직접 조회합니다."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        date_str = selected_date.isoformat()
        cursor.execute("SELECT content FROM diary WHERE date = ?", (date_str,))
        result = cursor.fetchone() 
        if result:
            return result[0] # content 텍스트
        else:
            return None
    except sqlite3.Error as e:
        st.error(f"데이터베이스 조회 중 오류 발생: {e}")
        return None
    finally:
        if conn:
            conn.close()

# --- 4. Streamlit UI 메인 함수 (NameError 수정됨) ---
def main():
    st.set_page_config(page_title="SQL 일기 에이전트", page_icon="✍️")
    st.title("SQL 일기 에이전트 ✍️")
    st.caption(f"오늘 날짜: {datetime.date.today().isoformat()}")

    # 1. DB 초기화
    setup_database()

    # 2. API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API 키가 필요합니다. .env 파일에 추가해주세요.")
        st.stop()

    # 3. SQL 에이전트 로드
    try:
        agent_executor = get_agent(api_key)
    except Exception as e:
        st.error(f"에이전트를 초기화할 수 없습니다: {e}")
        st.stop()

    # 4. session_state 초기화
    if "selected_diary" not in st.session_state:
        st.session_state.selected_diary = {"date": None, "content": None}
    if "last_calendar_event" not in st.session_state:
        st.session_state.last_calendar_event = None

    # --- [기능] 달력으로 일기 '조회'하기 ---
    with st.expander("🗓️ 달력에서 일기 조회하기 (날짜를 클릭하세요)", expanded=True):
        
        calendar_options = {
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"},
            "initialView": "dayGridMonth",
            "selectable": True,
            "navLinks": False, 
        }

        clicked_event = calendar(
            events=[], 
            options=calendar_options,
            key="diary_calendar"
        )
        
        # 4. 날짜 클릭 이벤트 처리
        if (clicked_event 
            and clicked_event.get("dateClick") 
            and clicked_event != st.session_state.last_calendar_event):
            
            clicked_date_str = clicked_event["dateClick"]["date"]
            
            selected_date = None
            try:
                # [타임존 변환 로직]
                if 'T' in clicked_date_str:
                    if clicked_date_str.endswith('Z'):
                        clicked_date_str = clicked_date_str[:-1] + '+00:00'
                    
                    utc_dt = datetime.datetime.fromisoformat(clicked_date_str)
                    kst_dt = utc_dt.astimezone(ZoneInfo("Asia/Seoul"))
                    selected_date = kst_dt.date()
                else:
                    selected_date = datetime.date.fromisoformat(clicked_date_str)
            
            except Exception as e:
                st.error(f"날짜 파싱 중 오류 발생: {e}")
                date_part = clicked_date_str.split('T')[0]
                selected_date = datetime.date.fromisoformat(date_part)

            if selected_date:
                content = get_diary_entry(selected_date)
                
                st.session_state.selected_diary = {"date": selected_date, "content": content}
                st.session_state.last_calendar_event = clicked_event
                
                st.rerun() 

        # 5. session_state에 저장된 일기 표시
        if st.session_state.selected_diary["date"]:
            selected_date = st.session_state.selected_diary["date"]
            content = st.session_state.selected_diary["content"]
            
            if content:
                # ----------------------------------------------------
                # ✅ [수정됨] 
                # 'selected_state' (X) -> 'selected_date' (O)
                # ----------------------------------------------------
                st.success(f"**{selected_date.isoformat()}의 일기:**")
                formatted_content = content.replace('\n', '\n> ')
                st.markdown(f"> {formatted_content}")
            else:
                st.info(f"{selected_date.isoformat()}에는 저장된 일기가 없습니다.")
        else:
            st.info("달력에서 날짜를 클릭하면 해당 일기를 조회합니다.")

    # --- [기능] 일기 '작성'하기 (이전과 동일) ---
    st.divider()
    st.markdown("### ✍️ 일기 작성/추가하기")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 일기 내용을 입력하고 '저장하기' 버튼을 눌러주세요."}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.form(key="diary_input_form"):
        user_prompt = st.text_area(
            "일기 입력:",
            placeholder="여기에 일기를 입력하세요...\n(예: 오늘 정말 바빴다. 점심에는...)",
            height=150,
        )
        submitted = st.form_submit_button("💾 일기 저장/추가하기")

    if submitted:
        if user_prompt: 
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            full_prompt = get_system_prompt() + f"\n\n[사용자 요청]\n{user_prompt}"
            
            try:
                with st.chat_message("assistant"):
                    with st.spinner("에이전트가 일기를 저장/추가하는 중..."):
                        response = agent_executor.invoke({"input": full_prompt})
                        agent_response = response.get("output", "오류가 발생했습니다.")
            except Exception as e:
                agent_response = f"에이전트 실행 중 오류 발생: {e}"

            st.session_state.messages.append({"role": "assistant", "content": agent_response})
            st.rerun()
        else:
            st.warning("일기 내용을 입력해주세요.")

# --- 5. Streamlit 앱 실행 ---
main()