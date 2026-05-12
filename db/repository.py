import json
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from .base import get_db
from .models import ChatHistory

class ChatRepository:
    @staticmethod
    def gen_session_id() -> str:
        """生成唯一会话ID"""
        return str(uuid.uuid4())[:16]

    @staticmethod
    def save_chat(
        db: Session,
        session_id: str,
        role: str,
        content: str,
        attachments_json: str | None = None,
    ):
        """保存单条聊天记录；attachments_json 为 JSON 字符串或 None。"""
        record = ChatHistory(
            session_id=session_id,
            role=role,
            content=content,
            attachments_json=attachments_json,
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
        out: list[dict] = []
        for r in records:
            row: dict = {"role": r.role, "content": r.content}
            aj = getattr(r, "attachments_json", None)
            if aj:
                try:
                    row["attachments"] = json.loads(aj)
                except (json.JSONDecodeError, TypeError):
                    row["attachments"] = None
            out.append(row)
        return out

    @staticmethod
    def list_sessions(db: Session, limit: int = 100) -> list:
        """按最近活跃时间列出会话：session_id、更新时间、消息数、首条用户消息预览。"""
        rows = (
            db.query(
                ChatHistory.session_id,
                func.max(ChatHistory.create_time).label("updated_at"),
                func.count(ChatHistory.id).label("msg_count"),
            )
            .group_by(ChatHistory.session_id)
            .order_by(func.max(ChatHistory.create_time).desc())
            .limit(limit)
            .all()
        )
        out = []
        for sid, updated_at, msg_count in rows:
            first_user = (
                db.query(ChatHistory.content)
                .filter(
                    ChatHistory.session_id == sid,
                    ChatHistory.role == "user",
                )
                .order_by(ChatHistory.create_time.asc())
                .first()
            )
            raw = (first_user[0] if first_user else "") or ""
            one_line = raw.replace("\n", " ").strip()
            if not one_line.strip():
                one_line = "（含附图）"
            preview = (
                (one_line[:72] + "…")
                if len(one_line) > 72
                else (one_line or "（尚无用户消息）")
            )
            out.append(
                {
                    "session_id": sid,
                    "updated_at": updated_at.isoformat() if updated_at else None,
                    "msg_count": int(msg_count),
                    "preview": preview,
                }
            )
        return out

# 全局实例
chat_repo = ChatRepository()