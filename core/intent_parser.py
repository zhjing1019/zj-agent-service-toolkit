import json

from core.llm import resilient_invoke
from core.resilience import is_degraded_reply


def parse_task_by_deepseek(task: str, history: list | None = None):
    from core.prompts import TOOL_PROMPT, format_dialogue_history

    h = format_dialogue_history(history, max_messages=8)
    prompt = TOOL_PROMPT.format(history=h, task=task)
    raw = (resilient_invoke(prompt) or "").strip()
    if is_degraded_reply(raw):
        return {
            "need_tool": False,
            "tool_name": None,
            "params": [],
            "__degraded__": True,
            "__message__": raw,
        }
    try:
        return json.loads(raw)
    except Exception:
        return {"need_tool": False, "tool_name": None, "params": []}