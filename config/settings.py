from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    SERVICE_NAME = os.getenv("SERVICE_NAME", "LangGraph-Agent-SQLite")
    VERSION = os.getenv("VERSION", "1.0.0")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    DB_TYPE = os.getenv("DB_TYPE", "sqlite")
    SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/agent.db")

    SECRET_KEY = os.getenv("SECRET_KEY", "default-key")
    SAFE_MODE = os.getenv("SAFE_MODE", "True") == "True"

settings = Settings()