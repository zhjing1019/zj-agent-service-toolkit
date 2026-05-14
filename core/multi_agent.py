import re

from core.llm import resilient_invoke, resilient_stream
from core.prompts import PLANNER_PROMPT, SUMMARY_PROMPT, format_dialogue_history
from core.resilience import is_degraded_reply


def planner_route(
    task: str,
    history: list | None = None,
    *,
    upload_note: str = "",
) -> tuple[str, str | None, bool]:
    """
    规划路由。
    返回 (agent_type, degraded_task_output_or_None, skip_summary_llm)。
    agent_type 含 degraded：直达汇总节点并跳过汇总 LLM。
    """
    h = format_dialogue_history(history, max_messages=10)
    un = (upload_note or "").strip() or "（无）"
    prompt = PLANNER_PROMPT.format(history=h, task=task, upload_note=un)
    text = (resilient_invoke(prompt) or "").strip()
    if is_degraded_reply(text):
        return ("degraded", text, True)
    result = text.lower()
    if result in ("tool", "rag", "chat", "analytics"):
        route = result
    else:
        m = re.search(r"\b(tool|rag|chat|analytics)\b", result)
        route = m.group(1) if m else "chat"
    return (route, None, False)


def planner_agent(task: str, history: list | None = None) -> str:
    """规划 Agent：判断路由类型 tool/rag/chat/degraded（结合多轮历史）。"""
    return planner_route(task, history)[0]


def summary_agent(task: str, output: str, history: list | None = None) -> str:
    """汇总 Agent：整理输出最终回答（结合多轮历史）。"""
    h = format_dialogue_history(history, max_messages=14)
    prompt = SUMMARY_PROMPT.format(history=h, task=task, output=output)
    return (resilient_invoke(prompt) or "").strip()


def summary_agent_stream(
    task: str, output: str, history: list | None = None
):
    """与 summary_agent 同提示词，以流式块输出，供 SSE 使用。"""
    h = format_dialogue_history(history, max_messages=14)
    prompt = SUMMARY_PROMPT.format(history=h, task=task, output=output)
    yield from resilient_stream(prompt)
