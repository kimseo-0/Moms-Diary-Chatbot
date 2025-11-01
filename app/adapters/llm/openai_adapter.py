from __future__ import annotations
from typing import List, Dict, Any, Optional
from threading import Lock
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings


class OpenAIAdapter:
    """
    OpenAI 모델 인스턴스를 공유(singleton) 방식으로 관리
    - 같은 모델 이름으로 여러 번 호출해도 동일 인스턴스를 반환
    - LLM과 Embedding 모델 둘 다 지원
    """

    _llm_instances: Dict[str, ChatOpenAI] = {}
    _emb_instances: Dict[str, OpenAIEmbeddings] = {}
    _lock = Lock()

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

    # ------------------------------------------------------------------
    # LLM 인스턴스 (Chat)
    # ------------------------------------------------------------------
    def get_llm(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        **kwargs,
    ) -> ChatOpenAI:
        """
        모델 이름으로 LLM 인스턴스 재사용.
        """
        with self._lock:
            if model not in self._llm_instances:
                self._llm_instances[model] = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    **kwargs,
                )
            return self._llm_instances[model]

    # ------------------------------------------------------------------
    # Embedding 인스턴스
    # ------------------------------------------------------------------
    def get_embedding_model(
        self,
        model: str = "text-embedding-3-small",
        **kwargs,
    ) -> OpenAIEmbeddings:
        """
        임베딩 모델 재사용.
        """
        with self._lock:
            if model not in self._emb_instances:
                self._emb_instances[model] = OpenAIEmbeddings(model=model, **kwargs)
            return self._emb_instances[model]

    # ------------------------------------------------------------------
    # 단일 호출 래퍼
    # ------------------------------------------------------------------
    def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        간단히 한 번의 대화를 수행하고 결과 텍스트만 반환.
        messages: [{"role": "system", "content": "..."} ...]
        """
        llm = self.get_llm(model=model, temperature=temperature, **kwargs)
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)

    # ------------------------------------------------------------------
    # Embedding 계산
    # ------------------------------------------------------------------
    def embed_texts(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        **kwargs,
    ) -> List[List[float]]:
        """
        여러 문장의 임베딩을 한 번에 계산.
        """
        emb_model = self.get_embedding_model(model=model, **kwargs)
        return emb_model.embed_documents(texts)
