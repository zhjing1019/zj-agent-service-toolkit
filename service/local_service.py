from agent.base_agent import BaseAgent

class LocalService:
    def __init__(self):
        self.agent = BaseAgent()

    def chat(self):
        """命令行聊天交互"""
        print("=" * 40)
        print("   本地 Agent 服务已启动")
        print("输入 'exit' 退出")
        print("=" * 40)

        while True:
            user_input = input("请输入：")
            if user_input.lower() in ["exit", "quit", "q"]:
                print("👋 退出服务")
                break
            result = self.agent.run(user_input)
            print(result)

            if user_input == "查看记忆":
                print("\n===== 对话历史记忆 =====")
                for item in self.agent.get_memory():
                    print(f"{item['role']}: {item['content']}")
                continue

            # 让agent先执行
            response = self.agent.run(result)
            print(f"Agent：{response}")