# app/core/tooling.py
from app.core.config import config
from app.core.dependencies import get_openai
from app.tools.tool_registry import get_all_tools

DEFAULT_LLM_MODEL = getattr(config, "DEFAULT_LLM_MODEL", "gpt-4o-mini")

def get_llm(model_name: str = DEFAULT_LLM_MODEL, temperature: float = 0.0):
    oa = get_openai()
    llm = oa.get_llm(model=model_name, temperature=temperature)
    return llm

def get_llm_with_tools(model_name: str = DEFAULT_LLM_MODEL, temperature: float = 0.0):
    oa = get_openai()
    llm = oa.get_llm(model=model_name, temperature=temperature)
    return llm.bind_tools(get_all_tools())
