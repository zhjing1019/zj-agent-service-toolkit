# security_check
#        ↓ (安全)
# llm_parse
#        ↓ (需要工具)
# run_tool → END
#        ↓ (不需要)
# direct_answer → END

# 1. 导入依赖
from langgraph.graph import StateGraph, END
from core.state import AgentState
from security.validator import security
from core.intent_parser import parse_task_by_deepseek
from toolkit.base_tool import TOOL_REGISTRY
from core.llm import llm
# 可视化导入（不需要额外导入，使用编译后图的get_graph()方法）

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

        # ====================== 设置入口 ======================
        workflow.set_entry_point("security_check")

        # ====================== 条件边 1：安全检查结果 ======================
        workflow.add_conditional_edges(
            "security_check",
            lambda s: s["is_safe"],
            {True: "llm_parse", False: END}
        )

        # ====================== 条件边 2：是否需要调用工具 ======================
        workflow.add_conditional_edges(
            "llm_parse",
            lambda s: s["need_tool"],
            {True: "run_tool", False: "direct_answer"}
        )

        # ====================== 普通边：执行完结束 ======================
        workflow.add_edge("run_tool", END)
        workflow.add_edge("direct_answer", END)


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
            return {"result": "无法识别工具"}

        try:
            res = TOOL_REGISTRY[tool_name](*params)
            return {"result": f"✅ 执行结果：{res}"}
        except Exception as e:
            return {"result": f"❌ 执行失败：{str(e)}"}

    # ====================== 节点 4：直接回答（不用工具） ======================
    def direct_answer_node(self, state: AgentState):
        context = state.get("rag_context", "")
        task = state["task"]

        prompt = f"""
你是专业智能问答助手，请严格遵循以下规则：
1. 优先参考下方【知识库参考内容】回答用户问题
2. 如果参考内容无相关信息，使用自身知识正常回答
3. 回答简洁准确，不要编造无关信息
4. 不要输出多余解释、不要重复提问

【知识库参考内容】
{context}

【用户问题】
{task}
"""
        reply = llm.invoke(prompt)
        return {"result": reply.content.strip()}

# 全局单例，整个项目共用一个图
agent_graph = AgentGraph()