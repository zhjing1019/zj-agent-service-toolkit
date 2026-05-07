import re

from core.llm import llm
from core.prompts import PLANNER_PROMPT, SUMMARY_PROMPT

def planner_agent(task: str) -> str:
    """规划Agent：判断路由类型 tool/rag/chat"""
    # prompt = PLANNER_PROMPT.format(task=task)
    # res = llm.invoke(prompt)
    # return res.content.strip().lower()
    prompt = PLANNER_PROMPT.format(task=task)
    res = llm.invoke(prompt)
    result = res.content.strip().lower()
    if result in ("tool", "rag", "chat"):
        return result
    m = re.search(r"\b(tool|rag|chat)\b", result)
    if m:
        return m.group(1)
    return "chat"

def summary_agent(task: str, output: str) -> str:
    """汇总Agent：整理输出最终回答"""
    prompt = SUMMARY_PROMPT.format(task=task, output=output)
    res = llm.invoke(prompt)
    return res.content.strip()