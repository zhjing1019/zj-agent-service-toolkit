import re

from core.llm import llm
from core.prompts import PLANNER_PROMPT, SUMMARY_PROMPT, format_dialogue_history

def planner_agent(task: str, history: list | None = None) -> str:
    """规划Agent：判断路由类型 tool/rag/chat（结合多轮历史）。"""
    h = format_dialogue_history(history, max_messages=10)
    prompt = PLANNER_PROMPT.format(history=h, task=task)
    res = llm.invoke(prompt)
    result = res.content.strip().lower()
    if result in ("tool", "rag", "chat"):
        return result
    m = re.search(r"\b(tool|rag|chat)\b", result)
    if m:
        return m.group(1)
    return "chat"

def summary_agent(task: str, output: str, history: list | None = None) -> str:
    """汇总Agent：整理输出最终回答（结合多轮历史）。"""
    h = format_dialogue_history(history, max_messages=14)
    prompt = SUMMARY_PROMPT.format(history=h, task=task, output=output)
    res = llm.invoke(prompt)
    return res.content.strip()


def summary_agent_stream(
    task: str, output: str, history: list | None = None
):
    """与 summary_agent 同提示词，以流式块输出，供 SSE 使用。"""
    h = format_dialogue_history(history, max_messages=14)
    prompt = SUMMARY_PROMPT.format(history=h, task=task, output=output)
    for chunk in llm.stream(prompt):
        text = getattr(chunk, "content", None)
        if isinstance(text, str) and text:
            yield text
        elif isinstance(text, list):
            for block in text:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text") or ""
                    if t:
                        yield t