import json
from core.llm import llm
from core.prompts import TOOL_PROMPT

def parse_task_by_deepseek(task: str):
    prompt = TOOL_PROMPT.format(task=task)
    response = llm.invoke(prompt)

    try:
        return json.loads(response.content.strip())
    except:
        return {"need_tool": False, "tool_name": None, "params": []}