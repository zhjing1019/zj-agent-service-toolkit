# 安全校验 
#    ↓
# 规划Agent（任务拆解分流）
#    ↓ 分支判断
# 工具执行Agent  /  RAG知识库Agent
#    ↓           /
# 汇总输出Agent → 结束

import time

from langgraph.graph import StateGraph, END
from config.settings import settings
from core.state import AgentState
from security.validator import security
from core.intent_parser import parse_task_by_deepseek
from toolkit.base_tool import TOOL_REGISTRY
from core.llm import resilient_invoke
from core.rag import query_knowledge
from core.coreference import resolve_retrieval_query
from core.multi_agent import planner_route, summary_agent
from core.prompts import CHAT_AGENT_PROMPT, RAG_ANSWER_PROMPT, format_dialogue_history
from core.checkpoint_store import get_graph_checkpointer
from core.resilience import is_degraded_reply, is_retryable_tool_error
# 可视化功能已内置在编译后的图对象中，无需额外导入

# 2. 定义工作流类
class AgentGraph:
    # 初始化：自动构建流程图
    def __init__(self):
        self.graph = self.build()
        # ======================
        # 自动生成工作流可视化图
        # ======================
        self.visualize()


    # 3. 核心：构建流程图
    def build(self):
        # 定义工作流，使用我们定义的状态类型 AgentState
        workflow = StateGraph(AgentState)

        # ====================== 注册 4 个节点 ======================
        # 安全检查节点
        workflow.add_node("security_check", self.security_check_node)
        # DeepSeek 大模型解析意图
        workflow.add_node("llm_parse", self.llm_parse_node)
        # 执行工具
        workflow.add_node("run_tool", self.run_tool_node)
        # 直接回答
        workflow.add_node("direct_answer", self.direct_answer_node)

        # ========== 新增多Agent节点 ==========
        # 规划Agent
        workflow.add_node("planner_agent", self.planner_agent_node)
        # RAG问答Agent
        workflow.add_node("rag_answer_agent", self.rag_answer_node)
        # 普通闲聊Agent
        workflow.add_node("chat_answer_agent", self.chat_answer_agent_node)
        # 汇总输出Agent
        workflow.add_node("summary_agent", self.summary_agent_node)
        # RAG检索节点
        workflow.add_node("rag_retrieve", self.rag_retrieve_node)

        # ====================== 设置入口 ======================
        workflow.set_entry_point("security_check")

        # ====================== 条件边 1：安全检查结果 ======================
        workflow.add_conditional_edges(
            "security_check",
            lambda s: s["is_safe"],
            {True: "planner_agent", False: END},
        )

        # 规划Agent 条件分支路由
        workflow.add_conditional_edges(
            "planner_agent",
            lambda s: s["agent_type"],
            {
                "tool": "llm_parse",
                "rag": "rag_retrieve",
                "chat": "chat_answer_agent",
                "degraded": "summary_agent",
            },
        )

        # 工具链路
        workflow.add_edge("llm_parse", "run_tool")
        workflow.add_edge("run_tool", "summary_agent")

        # RAG知识库链路
        workflow.add_edge("rag_retrieve", "rag_answer_agent")
        workflow.add_edge("rag_answer_agent", "summary_agent")

        # 普通闲聊链路
        workflow.add_edge("chat_answer_agent", "summary_agent")

        # 汇总结束
        workflow.add_edge("summary_agent", END)

        _cp = get_graph_checkpointer()
        # 完整图：带 Sqlite 检查点，支持 invoke(None, config) 断点续跑
        self.graph = workflow.compile(checkpointer=_cp)
        # 流式路径：汇总在 HTTP 层 stream，不挂 checkpointer，避免与「图外 summary」状态不一致
        self.graph_pre_summary = workflow.compile(
            interrupt_before=["summary_agent"]
        )
        return self.graph

    # ======================
    # 可视化方法
    # ======================
    def visualize(self):
        """生成流程图图片：agent_graph.png"""
        try:
            # 使用get_graph()获取图结构，然后生成mermaid格式的PNG图片
            self.graph.get_graph().draw_mermaid_png(output_file_path="agent_graph.png")
            print("✅ 工作流可视化图已生成：agent_graph.png")
        except Exception as e:
            # 如果生成PNG失败（可能缺少依赖），生成mermaid文本
            mermaid_code = self.graph.get_graph().draw_mermaid()
            with open("agent_graph.mmd", "w") as f:
                f.write(mermaid_code)
            print(f"⚠️ 生成PNG失败，已生成mermaid文件：agent_graph.mmd (错误: {str(e)})")

    # ====================== 节点 1：安全检查 ======================
    def security_check_node(self, state: AgentState):
        safe = security.check_input(state["task"])
        return {"is_safe": safe}
    
    # 2. 规划调度Agent
    def planner_agent_node(self, state: AgentState):
        hist = state.get("history") or []
        route, handoff, skip = planner_route(state["task"], hist)
        out: dict = {"agent_type": route}
        if handoff is not None:
            out["task_output"] = handoff
        if skip:
            out["skip_summary_llm"] = True
        return out
    
    # 3. RAG检索
    def rag_retrieve_node(self, state: AgentState):
        history = state.get("history") or []
        task = state["task"]
        resolved = resolve_retrieval_query(task, history)
        # 用独立问句检索，避免把整段历史拼进向量/BM25 导致噪声
        context = query_knowledge(resolved)
        return {"rag_context": context, "resolved_retrieval_query": resolved}
        # return {"rag_context": ""}

    # ====================== 节点 2：DeepSeek 大模型解析意图 ======================
    def llm_parse_node(self, state: AgentState):
        parsed = parse_task_by_deepseek(state["task"], state.get("history"))

        cleaned_parsed = {}
        for key, value in parsed.items():
            clean_key = key.strip().strip('"')
            cleaned_parsed[clean_key] = value

        if cleaned_parsed.get("__degraded__"):
            msg = cleaned_parsed.get("__message__") or settings.LLM_FAILURE_HANDOFF_MESSAGE
            return {
                "need_tool": False,
                "tool_name": "",
                "tool_params": [],
                "task_output": msg,
                "skip_summary_llm": True,
            }

        return {
            "need_tool": cleaned_parsed.get("need_tool", False),
            "tool_name": cleaned_parsed.get("tool_name"),
            "tool_params": cleaned_parsed.get("params", []),
        }

    # ====================== 节点 3：执行工具 ======================
    def run_tool_node(self, state: AgentState):
        if state.get("skip_summary_llm"):
            return {}

        tool_name = state["tool_name"]
        params = state["tool_params"]

        if tool_name not in TOOL_REGISTRY:
            return {"task_output": "无法识别工具"}

        max_r = (
            settings.TOOL_RETRY_CORE
            if tool_name in settings.TOOL_CORE_NAMES_SET
            else settings.TOOL_RETRY_OTHER
        )
        max_r = max(1, int(max_r))
        last_err: BaseException | None = None
        for attempt in range(max_r):
            try:
                res = TOOL_REGISTRY[tool_name](*params)
                return {"task_output": f"✅ 执行结果：{res}"}
            except Exception as e:
                last_err = e
                if attempt + 1 < max_r and is_retryable_tool_error(e):
                    time.sleep(
                        max(0.05, settings.LLM_RETRY_BACKOFF_SEC) * (attempt + 1)
                    )
                    continue
                break

        if last_err is not None and is_retryable_tool_error(last_err) and max_r > 1:
            return {"task_output": settings.TOOL_FAILURE_HANDOFF_MESSAGE}
        err_s = str(last_err) if last_err else "未知错误"
        return {"task_output": f"❌ 执行失败：{err_s}"}

    # ====================== 节点 4：直接回答（不用工具） ======================
    # 6. RAG问答Agent
    def rag_answer_node(self, state: AgentState):
        context = state.get("rag_context", "")
        task = state["task"]
        hist = state.get("history") or []
        htext = format_dialogue_history(hist, max_messages=12)
        prompt = RAG_ANSWER_PROMPT.format(
            context=context, history=htext, task=task
        )
        reply = resilient_invoke(prompt)
        content = (reply.content or "").strip()
        out: dict = {"task_output": content}
        if is_degraded_reply(content):
            out["skip_summary_llm"] = True
        return out

    # 7. 普通闲聊Agent
    def chat_answer_agent_node(self, state: AgentState):
        hist = state.get("history") or []
        htext = format_dialogue_history(hist, max_messages=14)
        prompt = CHAT_AGENT_PROMPT.format(history=htext, task=state["task"])
        reply = resilient_invoke(prompt)
        content = (reply.content or "").strip()
        out: dict = {"task_output": content}
        if is_degraded_reply(content):
            out["skip_summary_llm"] = True
        return out

    # 8. 汇总输出Agent
    def summary_agent_node(self, state: AgentState):
        to = (state.get("task_output") or "").strip()
        if state.get("skip_summary_llm") or is_degraded_reply(to):
            final = to if to else settings.LLM_FAILURE_HANDOFF_MESSAGE
            return {"result": final}
        hist = state.get("history") or []
        final = summary_agent(state["task"], state["task_output"], hist)
        return {"result": final}

    def direct_answer_node(self, state: AgentState):
        reply = resilient_invoke(state["task"])
        return {"result": (reply.content or "").strip()}

# 全局单例，整个项目共用一个图
agent_graph = AgentGraph()