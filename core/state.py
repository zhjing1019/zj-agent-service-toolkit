from typing import TypedDict, List, Dict

class AgentState(TypedDict):
    task: str
    is_safe: bool
    need_tool: bool
    tool_name: str
    tool_params: list
    result: str
    history: List[Dict]
    rag_context: str    # 新增：知识库检索上下文