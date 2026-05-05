from core.graph import agent_graph
from db.repository import chat_repo
from db.base import get_db

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

        # 调用 LangGraph 工作流
        res = agent_graph.graph.invoke({
            "task": task,
            "is_safe": False,
            "tool_name": "",
            "tool_params": [],
            "result": "",
            "history": history
        })

        agent_reply = res["result"]
        print(f"Agent：{agent_reply}")

        # 持久化保存问答
        chat_repo.save_chat(db, session_id, "user", task)
        chat_repo.save_chat(db, session_id, "agent", agent_reply)