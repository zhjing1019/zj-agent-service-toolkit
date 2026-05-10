from .base import engine, Base
from .models import ChatHistory, TaskRecord, AgentTaskRun, ApiLog, ErrorLog

def init_database():
    Base.metadata.create_all(bind=engine)
    print("✅ SQLite 数据库初始化完成")