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

class ApiLog(Base):
    __tablename__ = "api_log"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), index=True)
    task = Column(Text)
    response = Column(Text)
    status = Column(String(20))
    ip = Column(String(50))
    create_time = Column(DateTime, default=datetime.now)

class ErrorLog(Base):
    __tablename__ = "error_log"
    id = Column(Integer, primary_key=True)
    error_msg = Column(Text)
    traceback = Column(Text)
    create_time = Column(DateTime, default=datetime.now)