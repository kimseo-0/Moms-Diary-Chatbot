# app/tools/rag_tools.py
from langchain.agents import tool
from app.core.dependencies import get_chroma_retriever

# @tool("search_medical_sources", return_direct=False)
def search_medical_sources(query: str, top_k: int = 5):
    """
    의료 관련 질문에 대해 RAG 기반으로 근거 문서를 검색합니다.
    """
    retriever = get_chroma_retriever(collection_name="pregnancy_2025")
    docs = retriever.invoke(query)
    return [
        {"content": d.page_content, "source": d.metadata.get("source"), "page": d.metadata.get("page")}
        for d in docs[:top_k]
    ]
