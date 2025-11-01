# app/adapters/rag/chroma_adapter.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import chromadb
from app.core.logger import get_logger

logger = get_logger(__name__)

@dataclass
class RetrievedDoc:
    id: str
    content: str
    score: float
    source: Optional[str] = None
    page: Optional[int] = None


class ChromaAdapter:
    """
    Chroma DB query 검색
    """

    def __init__(self, persist_dir: str, embedding_fn=None):
        logger.info("ChromaAdapter 초기화: persist_dir=%s", persist_dir)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embedding_fn = embedding_fn

    def _open(self, collection_name: str):
        return self._client.get_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )

    @staticmethod
    def _to_similarity(distance: float) -> float:
        """distance → 0~1 정규화된 유사도로 변환"""
        return max(0.0, min(1.0, 1.0 - float(distance)))

    def query_similar(self, collection_name: str, query_text: str, top_k: int = 5) -> List[RetrievedDoc]:
        """
        지정된 컬렉션에서 query_text와 유사한 문서 검색.
        """
        logger.info("Chroma 검색 실행: collection=%s, top_k=%d", collection_name, top_k)
        coll = self._open(collection_name)
        result = coll.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        outputs: List[RetrievedDoc] = []
        for i, _id in enumerate(ids):
            md = metas[i] if i < len(metas) else {}
            outputs.append(
                RetrievedDoc(
                    id=str(_id),
                    content=docs[i],
                    score=self._to_similarity(dists[i]),
                    source=md.get("source"),
                    page=md.get("page"),
                )
            )
        return outputs
