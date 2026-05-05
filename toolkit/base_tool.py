from datetime import datetime

# ========== 计算器工具 ==========
def add(a: float, b: float) -> float:
    """加法"""
    return a + b

def subtract(a: float, b: float) -> float:
    """减法"""
    return a - b

def multiply(a: float, b: float) -> float:
    """乘法"""
    return a * b

def divide(a: float, b: float) -> float:
    """除法"""
    if b == 0:
        raise ValueError("除数不能为0")
    return a / b

# ========== 时间工具 ==========
def get_now_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_now_date() -> str:
    """获取当前日期"""
    return datetime.now().strftime("%Y-%m-%d")

# 工具注册字典
TOOL_REGISTRY = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
    "get_now_time": get_now_time,
    "get_now_date": get_now_date
}