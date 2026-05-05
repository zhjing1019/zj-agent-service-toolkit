from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from .base import Base

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), index=True)
    role = Column(String(20))
    content = Column(Text)
    create_time = Column(DateTime, default=datetime.now)

class TaskRecord(Base):
    __tablename__ = "task_record"
    id = Column(Integer, primary_key=True)
    task = Column(Text)
    tool = Column(String(50))
    status = Column(String(20))
    result = Column(Text)
    create_time = Column(DateTime, default=datetime.now)