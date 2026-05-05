from datetime import datetime

def add(a,b): return a+b
def subtract(a,b): return a-b
def multiply(a,b): return a*b
def divide(a,b):
    if b ==0: raise Exception("除零错误")
    return a/b

def get_now_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_now_date():
    return datetime.now().strftime("%Y-%m-%d")

TOOL_REGISTRY = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
    "get_now_time": get_now_time,
    "get_now_date": get_now_date,
}