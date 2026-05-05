from sqlalchemy.orm import Session
from .base import get_db
from .models import ChatHistory
import uuid

class ChatRepository:
    @staticmethod
    def gen_session_id() -> str:
        """生成唯一会话ID"""
        return str(uuid.uuid4())[:16]

    @staticmethod
    def save_chat(db: Session, session_id: str, role: str, content: str):
        """保存单条聊天记录"""
        record = ChatHistory(
            session_id=session_id,
            role=role,
            content=content
        )
        db.add(record)
        db.commit()

    @staticmethod
    def get_history(db: Session, session_id: str) -> list:
        """读取某会话全部历史"""
        records = db.query(ChatHistory)\
                   .filter(ChatHistory.session_id == session_id)\
                   .order_by(ChatHistory.create_time.asc())\
                   .all()
        return [{"role": r.role, "content": r.content} for r in records]

# 全局实例
chat_repo = ChatRepository()