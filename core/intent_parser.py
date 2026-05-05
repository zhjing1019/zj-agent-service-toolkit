import re

def parse_task(task: str) -> dict:
    """
    解析用户任务：识别工具 + 提取参数
    返回：{tool_name, tool_params}
    """
    task = task.lower().strip()

    # 1. 匹配四则运算
    calc_pat = r"(\d+\.?\d*)\s*([加减乘除+\-*/])\s*(\d+\.?\d*)"
    match = re.search(calc_pat, task)
    if match:
        a = float(match.group(1))
        op = match.group(2)
        b = float(match.group(3))

        op_map = {
            "加":"add", "+":"add",
            "减":"subtract", "-":"subtract",
            "乘":"multiply", "*":"multiply", "x":"multiply",
            "除":"divide", "/":"divide"
        }
        tool_name = op_map.get(op, None)
        if tool_name:
            return {"tool_name": tool_name, "tool_params": [a,b]}

    # 2. 匹配时间日期
    if any(k in task for k in ["几点", "现在时间"]):
        return {"tool_name": "get_now_time", "tool_params": []}
    if any(k in task for k in ["几号", "今天日期"]):
        return {"tool_name": "get_now_date", "tool_params": []}

    # 3. 无匹配工具
    return {"tool_name": None, "tool_params": []}