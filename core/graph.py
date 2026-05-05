from langgraph.graph import StateGraph, END
from core.state import AgentState
from security.validator import security
from core.intent_parser import parse_task
from toolkit import TOOL_REGISTRY

class AgentGraph:
    def __init__(self):
        self.graph = self.build()

    def build(self):
        workflow = StateGraph(AgentState)

        # 四个节点
        workflow.add_node("security_check", self.security_check_node)
        workflow.add_node("load_history", self.load_history_node)
        workflow.add_node("intent_parse", self.intent_parse_node)
        workflow.add_node("run_tool", self.run_tool_node)

        # 入口
        workflow.set_entry_point("security_check")

        # 安全通过 → 加载历史
        workflow.add_conditional_edges(
            "security_check",
            lambda s: s["is_safe"],
            {True: "load_history", False: END}
        )

        workflow.add_edge("load_history", "intent_parse")
        workflow.add_edge("intent_parse", "run_tool")
        workflow.add_edge("run_tool", END)

        return workflow.compile()

    # 1. 安全校验
    def security_check_node(self, state: AgentState):
        safe = security.check_input(state["task"])
        return {"is_safe": safe}

    # 2. 加载历史记忆
    def load_history_node(self, state: AgentState):
        # 后续可以在这里基于history做上下文理解
        return {"history": state["history"]}

    # 3. 意图解析
    def intent_parse_node(self, state: AgentState):
        parsed = parse_task(state["task"])
        return {
            "tool_name": parsed["tool_name"],
            "tool_params": parsed["tool_params"]
        }

    # 4. 执行工具
    def run_tool_node(self, state: AgentState):
        tool_name = state["tool_name"]
        tool_params = state["tool_params"]

        if not tool_name or tool_name not in TOOL_REGISTRY:
            return {"result": "我暂时无法理解并处理这个任务"}

        try:
            func = TOOL_REGISTRY[tool_name]
            res = func(*tool_params)
            return {"result": f"执行成功：{res}"}
        except Exception as e:
            return {"result": f"执行失败：{str(e)}"}

agent_graph = AgentGraph()