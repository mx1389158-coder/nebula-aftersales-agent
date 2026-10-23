# 星云智家售后服务智能体

一个可本地复现的 AI Agent + RAG + 全栈工程，实现版本感知检索、可治理长期记忆、带确认与幂等保护的工单工具、候选技能审批和固定回归评测。

默认模式不需要云 API：系统使用确定性模板生成器和 256 维哈希向量，适合先验证业务闭环。切换 `LLM_PROVIDER=ollama` 后可接入本地 3B/4B 模型；PostgreSQL 环境会把嵌入保存为 `vector(256)` 并创建 HNSW 索引。

## 已实现范围

| 方案阶段 | 当前实现 |
| --- | --- |
| P0 基础环境 | Python 3.11、Node 22、Conda 文件、Docker Compose、健康检查、CI |
| P1 最小闭环 | FastAPI、Vue 操作台、真实账号登录、LangGraph 状态图、可取消 token SSE、限流、引用、工具确认、人工转接、会话与断点持久化 |
| P2 检索工程 | 异步 ETL、结构化分块、BM25/Dense/RRF/Cross-Encoder/MMR、版本与生效时间过滤、发布与回滚、LightRAG/OpenViking 实验适配器 |
| P3 记忆与工具 | tenant/user 隔离、敏感信息拦截、同意开关、记忆治理、Mem0 适配器、工单确认/幂等/时间线、设备归属、审计日志 |
| P4 经验复用 | 正向反馈生成候选 Skill、静态检查、回归门禁、人工审批、灰度、停用和版本回滚 |
| P5 评测与交付 | 50 条冒烟集、400 条唯一盲测集、100 条技能任务集、R0-R5/M0-M3、可靠 Worker、质量/安全/时延指标、Docker、测试、ADR |

## 架构

```text
Vue 3 操作台
    │ JWT / SSE / REST
FastAPI ── 会话、知识、记忆、工单、技能、评测 API ── Redis 唤醒
    │
LangGraph ── 上下文补全 → 记忆检索 → 版本过滤 → 混合检索 → 决策 → 回答/拒答
    │
SQLAlchemy ── SQLite（零依赖开发）/ PostgreSQL + pgvector（Compose）
    │
Worker ── PostgreSQL 原子领取/租约/心跳/重试/死信 ── ETL、评测、过期清理
```

关键设计不是把用户画像、知识库和业务数据塞进同一个向量库：

- 产品知识按 `tenant_id + product_id + model + firmware_version` 过滤后才排序。
- 长期记忆按 `tenant_id + user_id` 硬隔离，带来源、置信度、有效期、同意状态和软删除。
- 工单属于确定性写工具，未确认时返回 `need_confirm`，重复幂等键只返回原工单。
- 本项目数据库是默认且完整的工单后端，不依赖企业 CRM；未来确有第三方系统时再通过工具契约接入。
- 未审核或没有回归测试的 Skill 不能激活。

## 目录

```text
apps/api/                 FastAPI 应用、路由、领域模型和文档服务
apps/worker/              评测后台 Worker
apps/web/                 Vue 3 + TypeScript 操作台
packages/agent_core/      LangGraph 状态与模型 Provider
packages/context/         分块、向量、混合检索、记忆治理
packages/tools/           设备、手册和工单工具协议
configs/                  模型、检索和 Prompt 版本配置
data/fixtures/            虚构品牌演示数据
evals/datasets/           固定回归集
infra/migrations/         Alembic 初始数据库迁移
tests/                    单元与端到端测试
docs/adr/                 架构决策记录
```

## 最快启动：本地开发模式

要求 Python 3.11 和 Node.js 22。PowerShell：

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,postgres]"
npm.cmd --prefix apps/web install
```

终端 1：

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.app.main:app --reload --port 8000
```

终端 2：

```powershell
.\.venv\Scripts\python.exe -m apps.worker.app.main
```

终端 3：

```powershell
npm.cmd --prefix apps/web run dev
```

打开 `http://localhost:5173`。API 文档位于 `http://localhost:8000/docs`。首次以演示模式启动会自动创建 SQLite 数据库、演示管理员、X2 设备和 72 份版本化虚构知识文档。演示账号为 `demo@example.com`，初始密码为 `demo-change-me`。

## Docker Compose

安装 Docker Desktop 并启用 WSL2 后：

```powershell
Copy-Item .env.example .env
docker compose up --build
```

该模式启动 PostgreSQL/pgvector、Redis、API、Worker 和 Web。若要同时启动 Ollama：

```powershell
docker compose --profile local-model up --build
```

生产或共享环境使用 `docker-compose.prod.yml` 叠加配置，必须更换密钥和数据库密码、关闭演示模式，并按需设置一次性初始管理员。完整步骤见 `docs/deployment-runbook.md`。

## 本地模型

默认 `.env` 使用 `LLM_PROVIDER=mock`，回答只拼装已检索证据，便于稳定测试。使用宿主机 Ollama 时：

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
```

先在 Ollama 中准备对应模型。模型名称、量化方式和许可证审核状态应同步登记到 `configs/model_registry.yaml`。

## 数据库迁移

新环境推荐使用迁移而非 `create_all`：

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

初始迁移在 SQLite 上使用 JSON 嵌入列，在 PostgreSQL 上使用 `vector(256)`，并创建余弦 HNSW 索引。

## 验证

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m mypy apps packages
.\.venv\Scripts\python.exe -m pytest --cov=apps --cov=packages
npm.cmd --prefix apps/web run build
npm.cmd --prefix apps/web audit --audit-level=high
```

测试重点覆盖：版本不串用、租户隔离、记忆用户隔离、敏感信息拦截、工单确认和幂等、状态图追问/回答、JWT API、Worker 评测闭环。

## 关键 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 邮箱和密码登录 |
| `POST` | `/api/v1/auth/demo-token` | 本地演示令牌 |
| `POST` | `/api/v1/chat` | 完整回答、引用和决策轨迹 |
| `POST` | `/api/v1/chat/stream` | SSE 事件流 |
| `POST/GET` | `/api/v1/documents` | 创建异步导入任务、查看知识版本 |
| `GET/POST` | `/api/v1/jobs/{id}` | 查询进度、重试死信任务 |
| `POST` | `/api/v1/documents/{id}/publish` | 发布或归档知识版本 |
| `POST` | `/api/v1/documents/{id}/rollback/{version}` | 回滚知识版本 |
| `GET/POST/PATCH/DELETE` | `/api/v1/memories` | 用户可治理记忆 |
| `GET/POST` | `/api/v1/tickets` | 工单查询和确认后创建 |
| `GET/POST` | `/api/v1/skills` | 候选技能、版本、门禁、灰度和回滚 |
| `POST` | `/api/v1/feedback` | 会话反馈及候选技能提取 |
| `GET/PATCH` | `/api/v1/handoffs` | 人工接管队列 |
| `POST` | `/api/v1/evals/run` | 创建固定回归任务 |
| `POST` | `/api/v1/evals/matrix` | 创建 R0-R5/M0-M3 实验矩阵 |
| `POST` | `/api/v1/evals/skill-matrix` | 创建无技能/人工技能/抽取技能实验 |

`/tickets` 使用本项目数据库完成工单闭环，已经是可验收的默认实现。Zammad、GLPI、Frappe Helpdesk 或企业自有 CRM 只属于未来可选集成，不影响当前功能完整性。

## 参考项目的使用边界

实现参考了同级 `reference-projects/` 中项目的公开设计：FastAPI 模板的配置与 API 分层、Mem0 的身份作用域、LightRAG 的递归分块、OpenViking 的资源/记忆/技能边界、pgvector 的向量类型、Langfuse 的 trace 概念和 create-vue 的工程约定。

本仓库没有复制这些项目的业务代码。详细映射见 `docs/reference-implementation.md`；如后续直接引入上游模块，必须重新核对其当前许可证并保留相应声明。

## 数据与实验

`python scripts/generate_synthetic_data.py` 可确定性重建全虚构数据：4 个产品族、8 个型号、24 个固件版本、72 份文档、400 FAQ、1000 工单、20 用户、200 记忆、50 条分层冒烟用例、400 条唯一正式/盲测用例和 100 条技能任务。规模与数据哈希记录在 `data/synthetic/manifest.json`，实验定义在 `configs/experiments.yaml`。

默认哈希嵌入是无下载、可重复的基线。安装 `.[local-embedding]` 并设置 `EMBEDDING_PROVIDER=bge` 可启用 BGE；`CROSS_ENCODER_ENABLED=true` 启用交叉编码器。两者共用 256 维兼容投影，切换后应重新索引文档并运行实验矩阵。

系统不会自动执行退款、换货、拆机或真实硬件控制；涉及冒烟、漏电、高压和拆机的请求会直接转人工。这是产品安全边界，不是待补功能。

部署、故障演练、数据跨境边界和演示脚本分别见 `docs/deployment-runbook.md`、`docs/failure-drills.md`、`docs/security-and-data-governance.md` 和 `docs/demo-script.md`。

