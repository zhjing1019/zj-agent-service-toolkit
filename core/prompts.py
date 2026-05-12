from __future__ import annotations

from typing import Any

def format_dialogue_history(
    history_list: list[dict[str, Any]] | None, max_messages: int = 16
) -> str:
    """将多轮消息格式化为中文提示用文本（含用户/助手轮次）。"""
    if not history_list:
        return "（暂无更早对话）"
    lines: list[str] = []
    for item in history_list[-max_messages:]:
        role = item.get("role", "")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}：{content}")
    return "\n".join(lines) if lines else "（暂无更早对话）"


TOOL_PROMPT = """
你是一个智能助手，根据用户问题，选择是否调用工具。
可参考「此前对话」理解省略说法或追问意图。

可用工具：
- add(a,b): 加法
- subtract(a,b): 减法
- multiply(a,b): 乘法
- divide(a,b): 除法
- get_now_time(): 获取当前时间
- get_now_date(): 获取当前日期

输出【严格JSON】，不要其他内容：
{{
    "need_tool": true / false,
    "tool_name": "工具名",
    "params": []
}}

此前对话（节选）：
{history}

当前用户问题：{task}
"""

# ========== 多Agent 规划提示词 ==========
PLANNER_PROMPT = """
你是任务规划调度Agent，请结合「此前对话」与「当前用户输入」，判断属于哪一类，只返回指定关键词：

可选类型：
- tool：需要使用计算器、时间、日期等工具
- rag：需要查询专业知识库、文档资料或知识库中的图片/示意图
- chat：普通闲聊、写诗、日常对话（含承接上下文的追问）

严格只返回一个单词：tool / rag / chat
不要解释、不要多余文字

此前对话（节选）：
{history}

当前用户输入：{task}
"""

SUMMARY_PROMPT = """
你是结果汇总Agent。请结合「此前对话」理解用户语境，把下面「中间执行结果」整理成通顺、自然、友好的最终回答。
不要改变原意，不要编造内容，精简流畅；若用户在追问，请承接上文。

此前对话（节选）：
{history}

本轮用户问题：{task}
中间执行结果（来自工具/RAG/闲聊子 Agent）：{output}

请输出整理后的最终回答：
"""

CHAT_AGENT_PROMPT = """
你是友好的对话助手。请结合「此前对话」理解省略、指代与追问，自然回复「当前用户」这句话。

此前对话：
{history}

当前用户说：{task}

请直接回复用户（不要复述系统说明）："""

RAG_ANSWER_PROMPT = """参考知识库内容：
{context}

此前对话（节选）：
{history}

用户当前问题：{task}

请基于参考内容专业回答；若知识库不足以回答，如实说明。
若上下文中含「多模态-知识库图片检索」段落，可引用其中路径与描述回答与图片相关的问题；描述为空时不要编造画面细节。"""