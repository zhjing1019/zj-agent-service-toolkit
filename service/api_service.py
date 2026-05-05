# 升级成 HTTP 接口服务

from flask import Flask, request, jsonify
from agent.base_agent import BaseAgent
from config.settings import settings

# 初始化Flask
app = Flask(__name__)
# 初始化智能体
agent = BaseAgent()

@app.route("/api/agent/run", methods=["POST"])

def agent_run():
    data = request.get_json()
    task = data.get("task", "")
    if not task:
        return jsonify({"code": 400, "msg": "task不能为空"}), 400

    result = agent.run(task)
    return jsonify({
        "code": 200,
        "msg": "ok",
        "data": result
    })

# 接口：查看记忆
@app.route("/api/agent/memory", methods=["GET"])
def agent_memory():
    memory_list = agent.get_memory()
    return jsonify({
        "code": 200,
        "msg": "ok",
        "data": memory_list
    })

# 启动服务
if __name__ == "__main__":
    app.run(
        host=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        debug=True
    )