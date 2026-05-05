from typing import TypedDict, List, Dict

class AgentState(TypedDict):
    task: str               # 用户原始输入
    is_safe: bool           # 安全校验结果
    tool_name: str          # 匹配到的工具名
    tool_params: List[float]# 工具参数
    result: str             # 最终返回结果
    history: List[Dict]     # 对话历史