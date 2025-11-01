# app/main.py
# uvicorn app.main:app --reload --port 8000
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.http import router as api_router

def create_app() -> FastAPI:
    app = FastAPI(title="Moms Diary Chatbot API", version="0.1.0")

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
