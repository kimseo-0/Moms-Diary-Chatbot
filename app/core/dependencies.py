from __future__ import annotations
import os
from functools import lru_cache
from typing import Optional
from typing import Optional

from app.adapters.llm.openai_adapter import OpenAIAdapter
from app.services.profile_repo import ProfileRepository
from app.services.diary_repo import DiaryRepository
from app.services.chat_repo import ChatRepository
from app.core.config import config

# 주의: import 시점에 무거운 어댑터/서비스 인스턴스를 생성하지 마세요.
# 아래의 지연 생성(getter)을 사용해 import-time 부작용을 피하고 테스트를 용이하게 합니다.

# -----------------------------------------
# 의존성 주입
# -----------------------------------------

# ── 전역 설정 (함수 밖에서 바로 가져오기)
CHROMA_DIR: str = getattr(config, "CHROMA_DIR", None) or os.getenv("CHROMA_DIR", "./storage/chroma")
DEFAULT_EMBED_MODEL: str = getattr(config, "DEFAULT_EMBED_MODEL", None) or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

@lru_cache(maxsize=1)
def get_openai() -> OpenAIAdapter:
    """전역 OpenAIAdapter 인스턴스 (싱글톤)"""
    return OpenAIAdapter()

def get_chroma_vectorstore(collection_name: Optional[str]):
    """
    LangChain Chroma VectorStore.
    OpenAIAdapter.get_embedding_model() 이 반환하는 OpenAIEmbeddings(LC 규격)를 그대로 사용.
    """
    coll = collection_name
    oa = get_openai()
    embeddings = oa.get_embedding_model(model=DEFAULT_EMBED_MODEL)  # ⬅️ 직접 사용
    # 무거운 의존성은 지연 임포트하여 import 시점 부작용을 방지합니다
    from langchain_community.vectorstores import Chroma

    return Chroma(
        collection_name=coll,
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
    )

def get_chroma_retriever(collection_name: Optional[str], *, k: int = 5):
    """
    LangChain VectorStoreRetriever (간단 검색용).
    """
    # 타입 수준 의존성도 지연 임포트합니다
    from langchain_core.vectorstores import VectorStoreRetriever  # type: ignore

    return get_chroma_vectorstore(collection_name).as_retriever(search_kwargs={"k": k})


@lru_cache(maxsize=1)
def get_profile_repo() -> ProfileRepository:
    return ProfileRepository(db_path=str(config.DB_PATH))


@lru_cache(maxsize=1)
def get_diary_repo() -> DiaryRepository:
    return DiaryRepository(db_path=str(config.DB_PATH))


@lru_cache(maxsize=1)
def get_chat_repo() -> ChatRepository:
    return ChatRepository(db_path=str(config.DB_PATH))
