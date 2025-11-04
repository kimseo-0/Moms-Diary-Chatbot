from __future__ import annotations
from typing import Any, Dict


def safe_model_dump(model: Any, *, exclude_none: bool = False) -> Dict[str, Any]:
    """pydantic v1/v2 모델 덤프 호환 래퍼.

    먼저 pydantic v2의 `model.model_dump(exclude_none=...)`를 시도하고,
    실패하면 v1의 `model.dict()`로 폴백합니다.
    객체가 이미 일반 dict이면 그대로 반환합니다.
    """
    if model is None:
        return {}
    if isinstance(model, dict):
        return model

    # 먼저 pydantic v2 API를 시도합니다
    try:
        return model.model_dump(exclude_none=exclude_none)
    except Exception:
        pass

    # 다음으로 pydantic v1 API를 시도합니다
    try:
        if exclude_none:
            return {k: v for k, v in model.dict().items() if v is not None}
        return model.dict()
    except Exception:
        # 최후 수단: __dict__로 시도합니다
        try:
            return getattr(model, "__dict__", {}) or {}
        except Exception:
            return {}
