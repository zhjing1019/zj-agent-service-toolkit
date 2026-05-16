# AI 问数功能：从零跟着做（一步一步）

本文对应仓库里已实现的能力：**业务词典进向量库 → 大模型写 SQL → 程序校验 → 只读查库 → 自然语言小结**。

---

## 第 0 步：先搞懂要做什么

| 步骤 | 你要做的事 |
|------|------------|
| A | 装好依赖、配好 `.env` 里的 LLM Key |
| B | 保证 SQLite 里已有 `ma_*` 表（跑过 `init_database`） |
| C | **建向量库**：把「表结构 + 业务 YAML」写入 `chroma_analytics` |
| D | 启动服务，调接口问数 |

代码位置速查：

- 业务词典 YAML：`knowledge/analytics_business.yaml`（可改、可加长）
- 建索引脚本：`python -m core.analytics.reindex`
- SQL 校验：`core/analytics/sql_guard.py`
- 问数编排：`core/analytics/nl2sql.py`
- HTTP：`service/analytics_api.py`（已挂到 `app.py`）

---

## 第 1 步：安装依赖

在项目根目录执行（已建过 `.venv` 可跳过第一行）：

```bash
cd /Users/zhangjing/zhangjing/zj-agent-service-toolkit
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

新增依赖主要是 **`sqlglot`**（解析/校验 SQL）、**`PyYAML`**（读业务词典）。

---

## 第 2 步：配置环境变量

复制或编辑项目根目录的 `.env`，至少保证 **DeepSeek 或 OpenAI** 可用（与现有聊天一致），例如：

- `DEEPSEEK_API_KEY=...`
- `DEEPSEEK_BASE_URL=...`（若用官方默认可省略）

可选（有默认值，一般不用改）：

- `SQLITE_PATH=./data/agent.db`（问数读这个库）
- `ANALYTICS_CHROMA_DIR=./chroma_analytics`（问数专用向量目录，**不要**和 `CHROMA_DB_DIR` 混用）
- `ANALYTICS_BUSINESS_YAML=./knowledge/analytics_business.yaml`

---

## 第 3 步：保证数据库里有 `ma_*` 表

```bash
.venv/bin/python -c "from db.init_db import init_database; init_database()"
```

用 DB Browser 打开 `data/agent.db`，确认左侧有 `ma_order`、`ma_customer` 等表。

---

## 第 4 步：写/改「业务词典」（映射到向量库）

编辑 **`knowledge/analytics_business.yaml`**：

- 每条 `entries` 里写：**用户口头说法 ↔ 该用哪张表、哪一列、怎么 JOIN**。
- 保存后，必须 **重新建索引**（下一步），向量库才会更新。

---

## 第 5 步：把词典 + 表结构写入向量库（必做）

在项目根目录执行：

```bash
.venv/bin/python -m core.analytics.reindex
```

成功时终端会打印写入的文档条数（表越多条数越多）。  
若本机加载嵌入模型报错或闪退，可换一台有充足内存的机器，或先关掉其它占内存程序再试。

也可在 **服务已启动** 时调用 HTTP（等价于上面命令里的建库 + 重建索引）：

```http
POST http://127.0.0.1:8000/api/analytics/reindex-analytics
```

---

## 第 6 步：启动 API 服务

```bash
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## 第 7 步：调用「自然语言问数」

```http
POST http://127.0.0.1:8000/api/analytics/nl-query
Content-Type: application/json

{"question": "徐汇院5月13日有多少订单、总金额多少？"}
```

返回 JSON 里重点字段：

- `ok`：整条链路是否成功  
- `sql`：最终执行的 SQL（已通过校验）  
- `validation_error`：若 `ok=false`，这里是校验或执行错误说明  
- `columns` / `rows`：表格数据  
- `has_more`：是否超过行数上限（默认 200 行以外还有数据）  
- `summary`：模型用中文总结（数字应来自 `rows`）  
- `rag_snippets`：本次检索到的词典片段（便于你调试「词典是否生效」）

---

## 第 8 步：你自己扩展时怎么记

1. **改业务口径** → 只改 `knowledge/analytics_business.yaml` → 再跑 **第 5 步**。  
2. **加新表/新列** → 改 SQLAlchemy 模型并 `init_database` → 再跑 **第 5 步**（表结构会自动进向量块）。  
3. **加强 SQL 安全规则** → 改 `core/analytics/sql_guard.py`（例如再加禁止函数、强制时间条件等）。  
4. **调整行数上限** → `.env` 里 `ANALYTICS_ROW_LIMIT`。

---

## 问数权限（RBAC + 可选分院数据范围）

问数路由 **`/api/analytics/*`** 与主对话 **`/api/agent/*`** 一样挂载 **`attach_principal`**：`RBAC_ENABLED=true` 时必须在 Header 带 **`X-API-Key`** 或 **`Authorization: Bearer <key>`**（与现有 RBAC 一致）。

| 权限常量 | 角色 | 说明 |
|----------|------|------|
| `analytics.query` | 管理员、开发者、**业务用户** | `POST /nl-query` 自然语言问数 |
| `analytics.reindex` | 管理员、**开发者**（不含业务用户） | `POST /reindex-analytics` 重建问数向量库 |

**业务用户分院白名单（行级 + 提示词约束）**  

在 `.env` 中设置（仅对 **`RBAC_BUSINESS_API_KEYS`** 对应角色生效）：

```env
RBAC_BUSINESS_ANALYTICS_BRANCH_CODES=SH-XH-01,SH-PD-02
```

- 未配置或留空：**不限制**分院（与管理员/开发者问数范围一致，仍受 `sql_guard` 与 `ma_` 表前缀约束）。  
- 已配置：会把允许的 `branch_code` 写入 NL2SQL 提示词；若查询结果列中含有 **`branch_code`**，接口还会在返回前**过滤掉不在白名单内的行**（`data_scope_row_filter_applied` 等字段见响应体）。  
- 内置「徐汇」固定 SQL 模板硬编码 `SH-XH-01`：若白名单不含 `SH-XH-01`，将**不会**走该模板，改由模型在提示词约束下生成 SQL。

**注意**：结果行过滤依赖结果集中是否出现 `branch_code` 列；无该列时会返回 `data_scope_warning`，生产环境仍应优先在 **SQL 层或独立只读从库 + 视图** 做硬隔离。

---

## 常见问题

**Q：提示没有向量检索结果？**  
A：没做第 5 步，或 `chroma_analytics` 被删了，重新 `python -m core.analytics.reindex`。

**Q：模型生成的 SQL 执行失败？**  
A：看 `validation_error`；常见是列名写错——对照返回里的 `sql` 与 DB Browser 表结构。

**Q：校验拒绝了我的 SQL？**  
A：当前策略只允许 **`ma_` 开头的物理表**；禁止多语句、禁止 INSERT/UPDATE 等。复杂子查询若误杀，可把规则改松（需改代码）。

---

## 安全说明（必读）

- 接口会调用大模型，**勿对公网裸奔**；生产环境应加鉴权。问数已接入与主 API 相同的 **RBAC**（见上文「问数权限」）。  
- 校验链能挡掉大部分危险 SQL，但仍建议 **内网使用**、并定期审计日志。
