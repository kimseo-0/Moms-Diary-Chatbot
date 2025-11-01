# app/tools/rag_tools.py
from langchain.agents import tool
from app.core.dependencies import get_chroma_retriever
from app.core.logger import get_logger

logger = get_logger(__name__)

# @tool("search_medical_sources", return_direct=False)
def search_medical_sources(query: str, top_k: int = 5):
    """
    의료 관련 질문에 대해 RAG 기반으로 근거 문서를 검색합니다.
    """
    logger.info("툴(search_medical_sources) 호출: query_len=%d, top_k=%d", len(query or ""), top_k)
    retriever = get_chroma_retriever(collection_name="pregnancy_2025")
    docs = retriever.invoke(query)
    logger.debug("툴(search_medical_sources) 결과 문서 수: %d", len(docs))
    return [
        {"content": d.page_content, "source": d.metadata.get("source"), "page": d.metadata.get("page")}
        for d in docs[:top_k]
    ]
