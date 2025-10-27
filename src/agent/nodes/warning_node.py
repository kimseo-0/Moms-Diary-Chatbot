from typing import Literal
from langchain_core.messages import SystemMessage

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.state import State, log

def urgent_warning_node(state: State) -> dict:
    # 닥터 에이전트로 전달될 경고 메시지를 생성하고 상태에 추가
    warning_message = (
        """🚨 **경고: 이는 심각한 증상일 수 있습니다.** 🚨
        저는 인공지능 챗봇이며, 전문 의료진의 진료를 대체할 수 없습니다.
        **즉시 병원을 방문하거나 의료진에게 상담** 받으시는 것이 안전합니다. 
        """
    )
    
    warning_msg = SystemMessage(content=warning_message)
    log(state, "[urgent_warning]: 심각성 경고 메시지 생성")

    # 이 노드 이후에는 doctor_agent로 고정 연결됩니다.
    return {"messages": [warning_msg], "status": "done"}