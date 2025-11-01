# app/core/tooling.py
from app.core.config import config
from app.core.dependencies import get_openai
from app.tools.tool_registry import get_all_tools
from app.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_LLM_MODEL = getattr(config, "DEFAULT_LLM_MODEL", "gpt-4o-mini")

def get_llm(model_name: str = DEFAULT_LLM_MODEL, temperature: float = 0.0):
    logger.info("LLM 요청: 모델=%s, 온도=%s", model_name, temperature)
    oa = get_openai()
    llm = oa.get_llm(model=model_name, temperature=temperature)
    logger.debug("LLM 제공자 반환: 모델=%s", model_name)
    return llm

def get_llm_with_tools(model_name: str = DEFAULT_LLM_MODEL, temperature: float = 0.0):
    logger.info("툴 바인딩된 LLM 요청: 모델=%s, 온도=%s", model_name, temperature)
    oa = get_openai()
    llm = oa.get_llm(model=model_name, temperature=temperature)
    logger.debug("툴 바인딩 수행: 모델=%s, 툴수=%d", model_name, len(get_all_tools()))
    return llm.bind_tools(get_all_tools())
