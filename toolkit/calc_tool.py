# 计算器工具 toolkit/calc_tool.py
def add(a:float, b:float) -> float:
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
        raise ValueError("除数不能为 0")
    return a / b

# 工具注册（给 Agent 用）
CALC_TOOLS = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide
}