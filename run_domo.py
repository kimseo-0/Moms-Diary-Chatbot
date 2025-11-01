# run_demo.py
from __future__ import annotations
from app.graphs.main_graph import compile_app_graph
from app.core.state import AgentState
from app.core.io_payload import InputEnvelope, InputPayload, InputMetadata

def make_input_envelope(session_id: str, text: str) -> InputEnvelope:
    # NOTE: type은 스키마상 필수라 임시로 "chat" 고정
    # 실제 intent/plan 생성은 plan_router_node가 text 기반으로 재판단함.
    meta = InputMetadata(
        type="chat",
        source="demo",
        date=None,
        week=22,
        language="ko",
        extra={}
    )
    payload = InputPayload(text=text, context=None, metadata=meta)
    return InputEnvelope(session_id=session_id, payload=payload)

if __name__ == "__main__":
    graph = compile_app_graph()

    def run(text: str):
        env = make_input_envelope("user-123", text)
        state_in = AgentState(session_id=env.session_id, input=env)
        state_out = AgentState(**graph.invoke(state_in))

        print(f"\n=== INPUT: {text}")
        if state_out.final:
            print("RESULT TEXT:", state_out.final.result.text)
            print("RESULT DATA:", state_out.final.result.data)
            print("RESULT META:", state_out.final.result.meta.model_dump())
        else:
            print("FINAL: <none>")

    # # 다양한 날짜 표현 테스트
    # test_cases = [
    #     "10월 31일 일기 써줘",
    #     "어제 일기 작성해줘",
    #     "오늘 일기 써줘",
    #     "지난주 금요일 일기 써줘",
    #     "2025-10-30 일기 써줘",
    #     "일기 써줘"  # 날짜 미지정(오늘)
    # ]

    test_cases = [
        "오늘도 안녕",
        '오늘은 아침에 기분좋게 일어났어',
        '잠을 많이 자서 몸이 가벼웠어',
        '곧 잘시간이네',
        '이제 하루를 마무리해야겠어',
        '오늘도 수고했어 아기야, 좋은 꿈 꿔'
        "마지막으로 일기를 써볼까?"
    ]
    for case in test_cases:
        run(case)
