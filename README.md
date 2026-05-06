# LangGraph-Agent-SQLite 生产级智能体框架
基于 LangGraph + SQLite + Ollama 本地大模型
轻量化、无依赖、可插拔、可直接部署的 Agent 服务框架

## 技术栈
- 核心框架：langgraph / langchain
- 本地大模型：Ollama
- 数据库：SQLite（无需额外部署）
- 服务：FastAPI + 命令行双模式
- 架构：分层解耦、可插拔工具、安全校验、会话持久化

## 目录结构

langgraph-agent-sqlite/
├── core/ # LangGraph 工作流、LLM、意图解析、提示词
├── db/ # SQLite 模型、CRUD、初始化
├── config/ # 配置、日志
├── security/ # 安全输入校验
├── services/ # 命令行 CLI、FastAPI 接口
├── tools/ # 可插拔工具集
├── data/ # SQLite 数据库文件
├── logs/ # 日志文件
├── .env # 环境配置
├── .gitignore # 忽略配置
├── requirements.txt # 依赖
├── main.py # 命令行入口
├── app.py # API 服务入口
└── start.sh # 一键启动脚本


# LangGraph-Agent-DeepSeek 生产级智能体框架
基于 LangGraph + LangChain + DeepSeek + SQLite
轻量无中间件、可插拔工具、会话持久化、安全风控、CLI/API 双模式

## 技术栈
- 编排框架：LangGraph
- 大模型：DeepSeek（LangChain 标准接口调用）
- 存储：SQLite 本地文件，无需部署数据库
- 服务：FastAPI + 命令行交互式双入口
- 架构：分层解耦、状态驱动、条件分支工作流

## 核心能力
- ✅ 输入安全风控检测
- ✅ DeepSeek LLM 智能意图解析
- ✅ 自动判断是否调用工具
- ✅ 可插拔工具扩展（计算/时间/日期等）
- ✅ SQLite 会话持久化，历史记忆留存
- ✅ LangGraph 状态机工作流编排
- ✅ 命令行交互 + HTTP API 接口
- ✅ 可直接服务器一键部署

## 环境配置
### 1. 安装依赖
```bash
python3 -m venv venv

source venv/bin/activate


python3.11 -m pip --version
python3.11 -m pip install ...
python3.11 -m pip install -r requirements.txt
pip install -r requirements.txt

source .venv/bin/activate
python3.11 -m pip install -r requirements.txt

python3.11 main.py
```

运行  python3 main.py
运行接口  python3 -m service.api_service
启动接口 uvicorn app:app --reload --host=0.0.0.0 --port=8000