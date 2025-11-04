import importlib
import traceback
import sys

modules = [
    "app.nodes.plan_router_node",
    "app.api.http",
    "streamlit_app.client_api",
    "streamlit_app.pages.diary",
    "app.nodes.diary_node",
    "streamlit_app.pages.chatbot",
    "app.services.diary_repo",
    "app.main",
    "app.adapters.rag.chroma_adapter",
    "app.core.tooling",
    "app.tools.db_tools",
    "app.tools.rag_tools",
    "app.nodes.urgent_triage_node",
    "app.nodes.medical_qna_node",
    "app.nodes.baby_smalltalk_node",
    "app.utils.db_utils",
    "app.tools.render_tools",
    "app.tools.tool_registry",
    "app.graphs.main_graph",
    "app.core.config",
    "app.core.state",
]

any_error = False
for m in modules:
    try:
        importlib.import_module(m)
        print(f"OK: {m}")
    except Exception:
        any_error = True
        print(f"ERROR importing {m}")
        traceback.print_exc()

if any_error:
    sys.exit(1)
else:
    print("ALL_MODULES_IMPORTED_OK")
