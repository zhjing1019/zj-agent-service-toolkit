from .base import engine, Base
from .models import ChatHistory, TaskRecord  # 必须导入，才能创建表
from . import med_aesthetic_sales_models  # noqa: F401  # med-aesthetic sales demo tables

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ SQLite 数据库初始化完成，表已创建")