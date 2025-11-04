import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()  # .env 로드

class AppConfig:
    # Base paths
    ROOT_DIR = Path(__file__).resolve().parents[2]
    STORAGE_DIR = ROOT_DIR / "storage"
    
    CHROMA_DIR = STORAGE_DIR / "chroma"
    CHROMA_COLLECTION = ""

    DB_PATH = STORAGE_DIR / "db" / "app.db"

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Default Models
    DEFAULT_LLM_MODEL = "gpt-4o-mini"
    DEFAULT_EMBED_MODEL = "text-embedding-3-small"

    # Environment
    ENV = os.getenv("ENV", "dev")

config = AppConfig()
