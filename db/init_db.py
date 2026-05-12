from sqlalchemy import text

from .base import engine, Base
from .models import ChatHistory, TaskRecord, AgentTaskRun, ApiLog, ErrorLog


def _ensure_chat_history_attachments_column() -> None:
    """已有库升级：为 chat_history 增加 attachments_json 列。"""
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(chat_history)")).fetchall()
        cols = {r[1] for r in rows}
        if "attachments_json" not in cols:
            conn.execute(
                text("ALTER TABLE chat_history ADD COLUMN attachments_json TEXT")
            )


def init_database():
    Base.metadata.create_all(bind=engine)
    _ensure_chat_history_attachments_column()
    print("✅ SQLite 数据库初始化完成")