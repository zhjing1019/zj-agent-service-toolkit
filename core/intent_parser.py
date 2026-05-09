import json
from core.llm import llm

def parse_task_by_deepseek(task: str, history: list | None = None):
    from core.prompts import TOOL_PROMPT, format_dialogue_history

    h = format_dialogue_history(history, max_messages=8)
    prompt = TOOL_PROMPT.format(history=h, task=task)
    response = llm.invoke(prompt)

    try:
        return json.loads(response.content.strip())
    except:
        return {"need_tool": False, "tool_name": None, "params": []}