from core.graph import agent_graph
from config.settings import settings
from core.task_timeout import AgentExecutionTimeoutError, invoke_langgraph_with_timeout
from db.repository import chat_repo
from db.base import get_db
import uuid

def run_cli():
    print("=" * 50)
    print("   LangGraph Agent 已启动（持久化会话版）")
    print("=" * 50)

    # 生成当前会话ID
    session_id = chat_repo.gen_session_id()
    print(f"当前会话ID：{session_id}")

    # 获取数据库会话
    db = next(get_db())

    while True:
        task = input("\n你：")
        if task in ["exit", "quit", "q"]:
            print("👋 退出会话")
            break

        # 读取历史记忆
        history = chat_repo.get_history(db, session_id)

        # 每条 CLI 输入使用独立 checkpoint thread（与 HTTP 不传 id 时行为一致）
        invoke_cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}

        initial = {
            "task": task,
            "is_safe": False,
            "need_tool": False,
            "tool_name": "",
            "tool_params": [],
            "result": "",
            "history": history,
            "rag_context": "",
            "resolved_retrieval_query": "",
            "sub_tasks": [],
            "agent_type": "",
            "task_output": "",
            "final_summary": "",
            "skip_summary_llm": False,
        }
        try:
            res = invoke_langgraph_with_timeout(
                agent_graph.graph,
                initial,
                invoke_cfg,
                settings.AGENT_GRAPH_TIMEOUT_SEC,
            )
        except AgentExecutionTimeoutError as e:
            print(str(e))
            continue

        agent_reply = res["result"]
        print(f"Agent：{agent_reply}")

        # 持久化保存问答
        chat_repo.save_chat(db, session_id, "user", task)
        chat_repo.save_chat(db, session_id, "agent", agent_reply)