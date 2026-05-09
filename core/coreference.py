"""多轮对话下的指代消解：检索前将当前问句改写为可独立检索的完整问句。"""
from __future__ import annotations

from typing import List, Dict

from config.settings import settings
from core.llm import resilient_invoke
from core.resilience import is_degraded_reply

COREFERENCE_PROMPT = """你是指代消解与问句改写助手。根据「对话历史」和「用户当前问句」，输出一条**可直接用于知识库检索**的完整问句。

规则：
1. 将「它/其/这个/那款/上面那个/前者/后者」等指代，替换为对话中**时间上最近、且用户仍在追问的那个具体实体**（例如某品牌、某型号手机）。
2. 若用户连续切换话题（先荣耀手机再小米手机），「它」优先指向**最近一次明确提到**的主体（如小米）。
3. 若当前句已含明确实体，只做必要补全或保持原句，不要编造对话里未出现的实体。
4. 不要回答问题、不要解释；只输出这一条检索问句；不要加引号或前缀。

对话历史：
{history}

用户当前问句：
{task}

检索问句："""


def _format_history(history_list: List[Dict], max_messages: int) -> str:
    lines: List[str] = []
    for item in history_list[-max_messages:]:
        role = (item.get("role") or "user").strip()
        content = (item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}：{content}")
    return "\n".join(lines) if lines else "（无）"


def resolve_retrieval_query(task: str, history_list: List[Dict]) -> str:
    """
    结合最近对话，把可能含指代的问句改写成独立检索问句。
    关闭开关、无历史或调用失败时返回原 task。
    """
    task = (task or "").strip()
    if not settings.RAG_COREFERENCE_ENABLE or not task:
        return task

    history = history_list or []
    if not history:
        return task

    history_text = _format_history(history, settings.RAG_COREFERENCE_MAX_MESSAGES)
    prompt = COREFERENCE_PROMPT.format(history=history_text, task=task)
    try:
        res = resilient_invoke(prompt)
        text = (res.content or "").strip()
        if is_degraded_reply(text):
            return task
        if not text:
            return task
        # 去掉偶发的引号包裹
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("「") and text.endswith("」")):
            text = text[1:-1].strip()
        return text if text else task
    except Exception:
        return task
