from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.state import State, log

embedding = OpenAIEmbeddings(model="text-embedding-3-small")
db_path = "vectorstore/chroma_pregnancy_2025"
collection_name = "pregnancy_2025"

vectorstore = Chroma(
    persist_directory=db_path,
    collection_name=collection_name,
    embedding_function=embedding
)

retriever = vectorstore.as_retriever(
    search_kwargs = {"k" : 5}
)

def retrieve(state : State) -> State:
    print("---RETRIEVE---")
    question = state["input"]
    log(state, f"[retrieve]: retrieve 검색 시작, {question[:20]}")
    
    documents = retriever.invoke(question)
    log(state, f"[retrieve]: 검색 결과 {len(documents)}개")

    return {**state, "documents": documents}

# 문서를 합치는 함수
def format_docs(docs):
    return "\n\---\n\n".join([f"컨텐츠: " + doc.page_content + f"\n페이지: {doc.metadata.get('page_label')}" for doc in docs])