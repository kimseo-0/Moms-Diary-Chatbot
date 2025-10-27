from typing import Annotated, TypedDict, Literal, List
from langgraph.graph.message import add_messages

class State(TypedDict, total=False):
    input: str
    session_id: str
    messages: Annotated[list, add_messages]
    status: Literal["urgent_warning", "qna", 'small_talk', "done"]
    log: List[str]
    documents: List[str]

def log(st: State, msg: str) -> None:
    """
    상태의 'log' 리스트에 메시지를 추가하고, 콘솔에 출력하여 실시간 디버깅을 돕습니다.
    """
    st.setdefault("log", []).append(msg)
    print(msg)