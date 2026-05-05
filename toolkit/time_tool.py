from datetime import datetime

def get_now_time() -> str:
    """获取当前年月日时分秒"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

def get_now_date() -> str:
    """获取当前年月日"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d")

TIME_TOOLS = {
    "get_now_time": get_now_time,
    "get_now_date": get_now_date
}