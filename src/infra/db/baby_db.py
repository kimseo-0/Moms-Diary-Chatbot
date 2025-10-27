# infra/baby_db.py
import sqlite3
from pathlib import Path
from typing import Dict, Any

DEFAULT_DB_PATH = Path("database/baby.db")  # 같은 파일을 함께 써서 한 DB로 관리

def init_baby_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """아기 프로필 테이블만 초기화/생성"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS baby_profile (
            session_id TEXT PRIMARY KEY,
            nickname TEXT,
            sex TEXT CHECK (sex IN ('남자','여자','모름')) DEFAULT '모름',
            week INTEGER DEFAULT 0,
            day  INTEGER DEFAULT 0,
            tags TEXT,                        -- JSON 배열 문자열
            lmp_date TEXT,                    -- YYYY-MM-DD
            due_date TEXT,                    -- YYYY-MM-DD
            hospital TEXT,
            doctor   TEXT,
            mom_blood_type TEXT,
            mom_rh  TEXT,
            allergies TEXT,
            meds TEXT,
            supplements TEXT,
            notes TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

def load_baby_profile(session_id: str,
                      db_path: Path | str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """세션의 아기 프로필 로드. 없으면 기본값 반환."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM baby_profile WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return {
                "session_id": session_id,
                "nickname": "",
                "sex": "모름",
                "week": 0,
                "day": 0,
                "tags": "[]",
                "lmp_date": None,
                "due_date": None,
                "hospital": "",
                "doctor": "",
                "mom_blood_type": "",
                "mom_rh": "",
                "allergies": "",
                "meds": "",
                "supplements": "",
                "notes": "",
            }
        return {k: row[k] for k in row.keys()}

def upsert_baby_profile(session_id: str, data: Dict[str, Any],
                        db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """아기 프로필 업서트(tags는 list면 JSON으로 저장). LMP만 있으면 예정일 +280일 자동계산."""
    import json, datetime
    payload = dict(data)
    payload["session_id"] = session_id

    # tags => JSON 문자열
    if isinstance(payload.get("tags"), (list, tuple)):
        payload["tags"] = json.dumps(payload["tags"], ensure_ascii=False)

    # LMP 있고 due 없음 → +280일
    lmp = payload.get("lmp_date")
    if lmp and not payload.get("due_date"):
        try:
            d = datetime.date.fromisoformat(lmp)
            payload["due_date"] = (d + datetime.timedelta(days=280)).isoformat()
        except Exception:
            pass

    cols = ["session_id","nickname","sex","week","day","tags","lmp_date","due_date",
            "hospital","doctor","mom_blood_type","mom_rh","allergies","meds","supplements","notes"]
    q_cols = ",".join(cols)
    placeholders = ",".join(["?"]*len(cols))
    updates = ",".join([f"{c}=excluded.{c}" for c in cols if c!="session_id"])

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO baby_profile ({q_cols})
            VALUES ({placeholders})
            ON CONFLICT(session_id) DO UPDATE SET
            {updates},
            updated_at=CURRENT_TIMESTAMP
        """, [payload.get(c) for c in cols])
        conn.commit()
