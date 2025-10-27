# utils/llm.py
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
def get_llm():
    return _llm

DIARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "너는 일기 작가야. 아래의 모자-엄마 대화 로그를 바탕으로 따뜻하고 간결한 하루 일기 한 편을 작성해."),
    ("system", "출력은 마크다운. 제목 1줄, 본문 3~6문장. 1인칭으로."),
    ("user", "{dialog}")
])

EMO_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "너는 감정 분석가야. 아래 대화 로그에서 엄마의 감정 상태를 분석해."),
    ("system", "출력은 JSON(코드블록 금지). 키: emotions(감정라벨 배열), scores(라벨별 0~1 점수 맵), summary(2~3문장), cues(근거 문장 배열, 최대 5개)"),
    ("user", "{dialog}")
])

def build_diary(dialog_text: str) -> str:
    chain = DIARY_PROMPT | get_llm()
    resp = chain.invoke({"dialog": dialog_text})
    return resp.content if hasattr(resp, "content") else str(resp)

def analyze_emotion(dialog_text: str) -> dict:
    import json
    chain = EMO_PROMPT | get_llm()
    resp = chain.invoke({"dialog": dialog_text})
    txt = resp.content if hasattr(resp, "content") else str(resp)
    try:
        return json.loads(txt)
    except Exception:
        return {"error": "JSON parse failed", "raw": txt}
