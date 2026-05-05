from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    SERVICE_NAME = os.getenv("SERVICE_NAME")
    VERSION = os.getenv("VERSION")
    HOST = os.getenv("HOST")
    PORT = int(os.getenv("PORT"))
    
    # 数据库
    DB_TYPE = os.getenv("DB_TYPE")
    SQLITE_PATH = os.getenv("SQLITE_PATH")
    
    # 安全
    SECRET_KEY = os.getenv("SECRET_KEY")
    SAFE_MODE = os.getenv("SAFE_MODE") == "True"

settings = Settings()