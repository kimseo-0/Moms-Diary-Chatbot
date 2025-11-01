# app/main.py
# uvicorn app.main:app --reload --port 8000
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.http import router as api_router
from app.utils.migrations import run_migrations
from app.core.config import config
from app.core.logger import get_logger
from contextlib import asynccontextmanager

def create_app() -> FastAPI:
    # define lifespan before creating app so it can be passed into FastAPI
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # startup
        try:
            logger.info("시작 시 마이그레이션 실행 중...")
            run_migrations(str(config.DB_PATH))
            logger.info("마이그레이션 적용 완료")
        except Exception:
            logger.exception("시작 시 마이그레이션 적용 실패")
        yield
        # shutdown
    logger.info("애플리케이션 종료 중")

    app = FastAPI(title="Moms Diary Chatbot API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 필요 시 도메인 제한
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    return app

app = create_app()
