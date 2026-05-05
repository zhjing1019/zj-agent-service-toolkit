from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    # 服务
    SERVICE_NAME = os.getenv("SERVICE_NAME")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # DeepSeek
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # DB
    SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/agent.db")

    # 安全
    SAFE_MODE = os.getenv("SAFE_MODE", "True") == "True"

    # 工具配置
    DEFAULT_FILE_NAME = os.getenv("DEFAULT_FILE_NAME", "output.txt")
    MAX_MEMORY = int(os.getenv("MAX_MEMORY", 10))

settings = Settings()