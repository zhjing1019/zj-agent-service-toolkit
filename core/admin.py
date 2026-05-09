import os
import shutil
from config.settings import settings

def reset_all_chat_session(db):
    """清空所有会话聊天记录"""
    from db.models import ChatHistory
    db.query(ChatHistory).delete()
    db.commit()
    return {"msg":"所有会话历史已清空"}

def switch_llm_model(provider: str):
    """动态切换主模型（与 core.llm 全局实例同步）。"""
    from core.llm import set_primary_llm_provider

    set_primary_llm_provider(provider)
    return {"msg": f"已切换模型提供商为：{provider}"}