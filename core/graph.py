# 安全校验 
#    ↓
# 规划Agent（任务拆解分流）
#    ↓ 分支判断
# 工具执行Agent  /  RAG知识库Agent
#    ↓           /
# 汇总输出Agent → 结束

# 1. 导入依赖
from langgraph.graph import StateGraph, END
from core.state import AgentState
from security.validator import security
from core.intent_parser import parse_task_by_deepseek
from toolkit.base_tool import TOOL_REGISTRY
from core.llm import llm
# from core.rag import query_knowledge_with_history
from core.multi_agent import planner_agent, summary_agent
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
        workflow.add_node("security_check", self.security_check_node)
        workflow.add_node("llm_parse", self.llm_parse_node)
        workflow.add_node("run_tool", self.run_tool_node)
        workflow.add_node("direct_answer", self.direct_answer_node)

        # ========== 新增多Agent节点 ==========
        workflow.add_node("planner_agent", self.planner_agent_node)
        workflow.add_node("rag_answer_agent", self.rag_answer_node)
        workflow.add_node("chat_answer_agent", self.chat_answer_agent_node)
        workflow.add_node("summary_agent", self.summary_agent_node)
        workflow.add_node("rag_retrieve", self.rag_retrieve_node)

        # ====================== 设置入口 ======================
        workflow.set_entry_point("security_check")

        # ====================== 条件边 1：安全检查结果 ======================
        workflow.add_conditional_edges(
            "security_check",
            lambda s: s["is_safe"],
            {True: "llm_parse", False: END}
        )

        # 规划Agent 条件分支路由
        workflow.add_conditional_edges(
            "planner_agent",
            lambda s: s["agent_type"],
            {
                "tool": "llm_parse",
                "rag": "rag_retrieve",
                "chat": "chat_answer_agent"
            }
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

        return workflow.compile()


        # 编译工作流
        return workflow.compile()
    
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
        agent_type = planner_agent(state["task"])
        return {"agent_type": agent_type}
    
    # 3. RAG检索
    def rag_retrieve_node(self, state: AgentState):
        # context = query_knowledge_with_history(state["task"], state["history"])
        # return {"rag_context": context}
        return {"rag_context": ""}

    # ====================== 节点 2：DeepSeek 大模型解析意图 ======================
    def llm_parse_node(self, state: AgentState):
        parsed = parse_task_by_deepseek(state["task"])
        
        # 清理键名，移除可能的空格和换行符
        cleaned_parsed = {}
        for key, value in parsed.items():
            clean_key = key.strip().strip('"')
            cleaned_parsed[clean_key] = value
        
        return {
            "need_tool": cleaned_parsed.get("need_tool", False),
            "tool_name": cleaned_parsed.get("tool_name"),
            "tool_params": cleaned_parsed.get("params", []),
        }

    # ====================== 节点 3：执行工具 ======================
    def run_tool_node(self, state: AgentState):
        tool_name = state["tool_name"]
        params = state["tool_params"]

        if tool_name not in TOOL_REGISTRY:
            return {"task_output": "无法识别工具"}

        try:
            res = TOOL_REGISTRY[tool_name](*params)
            return {"task_output": f"✅ 执行结果：{res}"}
        except Exception as e:
            return {"task_output": f"❌ 执行失败：{str(e)}"}

    # ====================== 节点 4：直接回答（不用工具） ======================
    # 6. RAG问答Agent
    def rag_answer_node(self, state: AgentState):
        context = state.get("rag_context", "")
        task = state["task"]
        prompt = f"""
参考知识库内容：
{context}
用户问题：{task}
请基于参考内容专业回答。
"""
        reply = llm.invoke(prompt)
        return {"task_output": reply.content.strip()}

    # 7. 普通闲聊Agent
    def chat_answer_agent_node(self, state: AgentState):
        reply = llm.invoke(state["task"])
        return {"task_output": reply.content.strip()}

    # 8. 汇总输出Agent
    def summary_agent_node(self, state: AgentState):
        final = summary_agent(state["task"], state["task_output"])
        return {"result": final}

    def direct_answer_node(self, state: AgentState):
        reply = llm.invoke(state["task"])
        return {"result": reply.content}

# 全局单例，整个项目共用一个图
agent_graph = AgentGraph()