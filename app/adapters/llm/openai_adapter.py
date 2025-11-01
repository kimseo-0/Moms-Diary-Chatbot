from __future__ import annotations
from typing import List, Dict, Any, Optional
from threading import Lock
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.logger import get_logger

logger = get_logger(__name__)


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
        # Do not raise on import; store key if present and raise only on actual usage.
        self.api_key = os.getenv("OPENAI_API_KEY")
        logger.info("OpenAIAdapter 초기화 (API 키 존재 여부=%s)", bool(self.api_key))

    def _ensure_api_key(self):
        if not (self.api_key or os.getenv("OPENAI_API_KEY")):
            logger.error("OpenAI API 키가 설정되어 있지 않습니다. 환경변수 OPENAI_API_KEY 확인 필요")
            raise RuntimeError("OPENAI_API_KEY not found in environment variables. Set OPENAI_API_KEY before calling OpenAIAdapter methods.")

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
        # Ensure API key exists before creating model instances
        self._ensure_api_key()
        with self._lock:
            if model not in self._llm_instances:
                logger.info("새 LLM 인스턴스 생성: model=%s, temperature=%s", model, temperature)
                self._llm_instances[model] = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    **kwargs,
                )
            logger.debug("LLM 인스턴스 반환: model=%s", model)
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
        # Ensure API key exists before creating embedding instances
        self._ensure_api_key()
        with self._lock:
            if model not in self._emb_instances:
                logger.info("임베딩 모델 생성: model=%s", model)
                self._emb_instances[model] = OpenAIEmbeddings(model=model, **kwargs)
            logger.debug("임베딩 모델 반환: model=%s", model)
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
        # Ensure API key before making a call
        self._ensure_api_key()
        logger.info("LLM 호출: model=%s, temperature=%s, messages=%d", model, temperature, len(messages))
        try:
            llm = self.get_llm(model=model, temperature=temperature, **kwargs)
            response = llm.invoke(messages)
            logger.debug("LLM 호출 성공: model=%s", model)
            return response.content if hasattr(response, "content") else str(response)
        except Exception:
            logger.exception("LLM 호출 중 예외 발생: model=%s", model)
            raise

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
        # Ensure API key before embedding
        self._ensure_api_key()
        logger.info("임베딩 실행: model=%s, texts=%d", model, len(texts))
        try:
            emb_model = self.get_embedding_model(model=model, **kwargs)
            res = emb_model.embed_documents(texts)
            logger.debug("임베딩 완료: model=%s, 개수=%d", model, len(res))
            return res
        except Exception:
            logger.exception("임베딩 중 예외 발생: model=%s", model)
            raise
