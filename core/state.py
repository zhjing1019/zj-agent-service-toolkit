from typing import TypedDict, List, Dict, NotRequired

class AgentState(TypedDict):
    task: str
    is_safe: bool
    need_tool: bool
    tool_name: str
    tool_params: list
    result: str
    history: List[Dict]
    rag_context: str    # 新增：知识库检索上下文
    resolved_retrieval_query: str  # 指代消解后的检索问句（调试用，可与 task 不同）
    # 多Agent 新增字段
    sub_tasks: List[str]       # 拆解的子任务列表
    agent_type: str            # 路由类型：tool / rag / analytics / chat / degraded
    task_output: str           # 单个子任务输出
    final_summary: str         # 最终汇总结果
    skip_summary_llm: bool     # True 时汇总节点直接透出 task_output，不再调用大模型
    # 用户上传图（绝对路径）；RAG 检索命中的知识库图片元数据
    user_image_paths: NotRequired[List[str]]
    rag_referenced_images: NotRequired[List[Dict]]