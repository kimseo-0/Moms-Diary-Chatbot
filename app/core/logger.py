from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import config


LOG_DIR = Path(config.ROOT_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(level: int = logging.INFO):
    """Configure root logger with console and rotating file handlers."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    fh = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    root.setLevel(level)


def get_logger(name: str | None = None) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
