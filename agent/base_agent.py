# 编写 Agent 核心（大脑）
import re
from config.settings import settings
from config.logger import logger

# 初始化智能体
class BaseAgent:
    def __init__(self, name="MiniAgent"):
        self.name = name
        self.tools = self._register_tools()
        self.memory = []
        self.max_memory = settings.MAX_MEMORY  # 从配置读
        
    def _register_tools(self):
        """注册工具：Agent 能使用的所有工具在这里统一管理"""
        from toolkit.calc_tool import CALC_TOOLS
        from toolkit.file_tool import FILE_TOOLS
        from toolkit.time_tool import TIME_TOOLS
        return {**CALC_TOOLS, **FILE_TOOLS, **TIME_TOOLS}
    
    def think(self, task: str):
        """
        智能思考：
        1. 识别任务类型（计算/文件）
        2. 自动提取数字
        """
        task = task.lower().strip()
        # ----------------------
        # 1. 识别计算任务 + 自动提取数字
        # ----------------------
        calc_pattern = r"(\d+\.?\d*)\s*([加|减|乘|除|\+|\-|\*|/])\s*(\d+\.?\d*)"
        match = re.search(calc_pattern, task)
        if match:
            a = float(match.group(1))
            op = match.group(2)
            b = float(match.group(3))

            if op in ["+", "加"]:
                return {"tool": "add", "params": [a, b]}
            elif op in ["-", "减"]:
                return {"tool": "subtract", "params": [a, b]}
            elif op in ["*", "x", "乘"]:
                return {"tool": "multiply", "params": [a, b]}
            elif op in ["/", "除"]:
                return {"tool": "divide", "params": [a, b]}
        
        # ----------------------
        # 2. 文件任务
        # ----------------------
        if any(w in task for w in ["写文件", "保存", "写入"]):
            return {"tool": "write_file", "params": [settings.DEFAULT_FILE_NAME, f"任务内容：{task}"]}

        if any(w in task for w in ["读文件", "读取", "看文件"]):
            return {"tool": "read_file", "params": [settings.DEFAULT_FILE_NAME]}
        
        # 时间工具识别
        if any(w in task for w in ["现在时间", "当前时间", "几点了"]):
            return {"tool": "get_now_time", "params": []}
        if any(w in task for w in ["今天日期", "几号", "今日日期"]):
            return {"tool": "get_now_date", "params": []}

        # 无法识别
        return {"tool": None, "params": None}
    
    def run(self, task: str):
        # 1. 把用户问题存入记忆
        self.add_memory("user", task)
        logger.info(f"收到用户任务: {task}")
        print(f"\n【{self.name}】执行任务：{task}")
        decision = self.think(task)
        tool_name = decision.get("tool")
        params = decision.get("params", [])

        if not tool_name:
            return "❌ 我暂时无法处理这个任务"

        print(f"✅ 调用工具：{tool_name}")
        print(f"📌 参数：{params}")

        try:
            result = self.tools[tool_name](*params)
            logger.info(f"工具调用成功: {tool_name}, 参数={params}, 结果={result}")
            return f"✅ 执行成功：{result}"
        except Exception as e:
            logger.error(f"工具调用异常: {tool_name}, 错误={str(e)}")
            return f"❌ 执行失败：{str(e)}"
        
    def add_memory(self, role: str, content: str):
        """添加记忆：role=user/agent"""
        self.memory.append({"role": role, "content": content})
        # 超过最大条数，删掉最早的
        if len(self.memory) > self.max_memory:
            self.memory = self.memory[-self.max_memory:]
    
    def get_memory(self):
        """获取全部历史记忆"""
        return self.memory