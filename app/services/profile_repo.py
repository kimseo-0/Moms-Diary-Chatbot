from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from app.utils.db_utils import get_connection, upsert_from_model, fetch_one
from app.core.logger import get_logger

logger = get_logger(__name__)


class BabyProfile(BaseModel):
    session_id: str
    name: Optional[str] = None
    week: Optional[int] = Field(default=None, ge=0, le=42)
    gender: Optional[str] = "U"
    tags_json: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MotherProfile(BaseModel):
    session_id: str
    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=100)
    medical_notes: Optional[str] = None
    prefs_json: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProfileRepository:
    def __init__(self, db_path: str = "storage/db/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure DB schema exists
        try:
            from app.utils.db_utils import ensure_db_initialized
            ensure_db_initialized(str(self.db_path))
        except Exception:
            pass

    def get_baby(self, session_id: str) -> Optional[BabyProfile]:
        with get_connection(str(self.db_path)) as conn:
            row = fetch_one(conn, "baby_profile", "session_id", session_id)
        logger.debug("get_baby 호출: session=%s, found=%s", session_id, bool(row))
        return BabyProfile(**row) if row else None

    def get_mother(self, session_id: str) -> Optional[MotherProfile]:
        with get_connection(str(self.db_path)) as conn:
            row = fetch_one(conn, "mother_profile", "session_id", session_id)
        logger.debug("get_mother 호출: session=%s, found=%s", session_id, bool(row))
        return MotherProfile(**row) if row else None

    def upsert_baby(self, model: BabyProfile):
        with get_connection(str(self.db_path)) as conn:
            upsert_from_model(conn, "baby_profile", model)
        logger.info("아기 프로필 upsert: session=%s, name=%s, week=%s", model.session_id, model.name, model.week)

    def upsert_mother(self, model: MotherProfile):
        with get_connection(str(self.db_path)) as conn:
            upsert_from_model(conn, "mother_profile", model)
        logger.info("산모 프로필 upsert: session=%s, name=%s", model.session_id, model.name)
