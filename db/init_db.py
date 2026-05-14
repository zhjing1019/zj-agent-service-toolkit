from sqlalchemy import text

from .base import engine, Base
from .models import ChatHistory, TaskRecord, AgentTaskRun, ApiLog, ErrorLog
from . import med_aesthetic_sales_models  # noqa: F401  # register med-aesthetic sales tables


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
    from .seed_med_aesthetic_sales import seed_if_empty, topup_ma_empty_tables

    if seed_if_empty():
        print("✅ 已写入医美销售演示种子数据（首启一次）")
    n_top = topup_ma_empty_tables()
    if n_top:
        print(f"✅ 已补全 {n_top} 类空表演示数据（topup）")
    print("✅ SQLite 数据库初始化完成")