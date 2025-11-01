"""app/utils/migrations.py

Simple migration runner for the project.

This module provides a very small, safe migration helper that ensures the
database schema from `storage/db/schema.sql` is applied (if present), or that
a minimal fallback schema is created. It is intentionally conservative and
idempotent to avoid destructive changes during startup.
"""
from pathlib import Path
from typing import Optional, List
from app.core.config import config
from app.utils.db_utils import ensure_db_initialized, get_connection
from app.core.logger import get_logger
import sqlite3

logger = get_logger(__name__)


def _applied_migrations(conn: sqlite3.Connection) -> List[str]:
    cur = conn.execute("SELECT name FROM migrations ORDER BY applied_at ASC")
    rows = cur.fetchall()
    return [r[0] if isinstance(r, tuple) else r["name"] for r in rows]


def run_migrations(db_path: Optional[str] = None) -> None:
    """Run migrations (idempotent).

    Behavior:
    - Ensure base schema exists via `ensure_db_initialized` (idempotent).
    - Create a lightweight `migrations` table if missing.
    - Apply any .sql scripts found in the `migrations/` directory next to the DB file,
      in lexical order. Each applied script is recorded in the `migrations` table.
    """
    path = Path(str(db_path)) if db_path else Path(config.DB_PATH)
    db_path_str = str(path)
    logger.info("DB 마이그레이션 실행: %s", db_path_str)

    try:
        # Apply base schema or fallback
        ensure_db_initialized(db_path_str)

        # Open a connection and ensure migrations table exists
        with get_connection(db_path_str) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

            # Find migration files in sibling 'migrations' directory
            migrations_dir = path.parent / "migrations"
            if not migrations_dir.exists():
                logger.debug("마이그레이션 디렉토리 없음: %s", str(migrations_dir))
                logger.info("DB 초기화/업데이트 완료: %s", db_path_str)
                return

            sql_files = sorted([p for p in migrations_dir.iterdir() if p.suffix.lower() == ".sql"])
            applied = _applied_migrations(conn)

            for sql_file in sql_files:
                name = sql_file.name
                if name in applied:
                    logger.debug("마이그레이션 이미 적용됨: %s", name)
                    continue

                logger.info("마이그레이션 적용 중: %s", name)
                try:
                    with sql_file.open("r", encoding="utf-8") as fh:
                        sql = fh.read()
                    if sql.strip():
                        conn.executescript(sql)
                        conn.execute("INSERT INTO migrations (name) VALUES (?)", (name,))
                        conn.commit()
                        logger.info("마이그레이션 적용 완료: %s", name)
                except Exception:
                    logger.exception("마이그레이션 적용 실패: %s", name)
                    # continue to next script but record nothing

        logger.info("DB 초기화/업데이트 완료: %s", db_path_str)
    except Exception:
        logger.exception("DB 마이그레이션 중 오류 발생: %s", db_path_str)


def find_schema_file(db_path: Optional[str] = None) -> Optional[Path]:
    """Return Path to schema.sql next to the DB file if it exists, else None."""
    p = Path(str(db_path)) if db_path else Path(config.DB_PATH)
    schema = p.parent / "schema.sql"
    return schema if schema.exists() else None
