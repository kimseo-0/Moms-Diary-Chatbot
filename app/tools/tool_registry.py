# app/tools/tool_registry.py
from app.tools.db_tools import (
    save_chat_tool, get_recent_chats_tool,
    get_chats_by_date_tool,
    save_diary_tool, get_diary_list_tool,
    get_profile_tool, update_baby_profile_tool, update_mother_profile_tool
)
# from app.tools.rag_tools import search_medical_sources
from app.tools.render_tools import render_chat_output_tool

TOOLS = [
    save_chat_tool,
    get_recent_chats_tool,
    get_chats_by_date_tool,
    save_diary_tool,
    get_diary_list_tool,
    get_profile_tool,
    update_baby_profile_tool,
    # search_medical_sources,
    render_chat_output_tool,
    update_mother_profile_tool
]

def get_all_tools():
    """LangGraph 및 LLM에서 호출 가능한 모든 Tool 리스트"""
    return TOOLS
