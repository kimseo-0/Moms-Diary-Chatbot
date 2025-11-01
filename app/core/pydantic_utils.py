from __future__ import annotations
from typing import Any, Dict


def safe_model_dump(model: Any, *, exclude_none: bool = False) -> Dict[str, Any]:
    """Compatibility wrapper for pydantic v1/v2 model dump.

    Tries `model.model_dump(exclude_none=...)` (v2), falls back to `model.dict()` (v1).
    If the object is already a plain dict, returns it.
    """
    if model is None:
        return {}
    if isinstance(model, dict):
        return model

    # Try pydantic v2 API
    try:
        return model.model_dump(exclude_none=exclude_none)
    except Exception:
        pass

    # Try pydantic v1 API
    try:
        if exclude_none:
            return {k: v for k, v in model.dict().items() if v is not None}
        return model.dict()
    except Exception:
        # Last resort: try __dict__
        try:
            return getattr(model, "__dict__", {}) or {}
        except Exception:
            return {}
