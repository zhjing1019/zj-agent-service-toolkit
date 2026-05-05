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

运行  python3 main.py
运行接口  python3 -m service.api_service
启动接口 uvicorn app:app --reload --host=0.0.0.0 --port=8000