# 技术方案对标完成清单

本清单以《售后服务智能体-完整项目技术方案》为验收基线，记录仓库中可直接验证的实现位置。

| 阶段 | 已落地能力 | 验收入口 |
| --- | --- | --- |
| P0 | Python/Node/Conda、Compose 开发/生产覆盖、PostgreSQL + pgvector、Redis、健康检查、锁文件、CI | `docker-compose.yml`、`docker-compose.prod.yml`、`.github/workflows/ci.yml` |
| P1 | 登录、限流、LangGraph 路由、设备上下文、版本证据、引用、断开可取消 SSE、工单确认、人工转接、持久化断点 | `/auth/login`、`/chat`、`/chat/stream`、`agent_checkpoints`、`human_handoffs` |
| P2 | 异步 ETL、任务进度、BM25/Dense/RRF/MMR、BGE/Cross-Encoder、硬过滤、生效时间、发布/回滚、LightRAG/OpenViking 外部基线 | `/documents`、`/jobs/{id}`、`packages/context/retrieval.py` |
| P3 | tenant/user 隔离、敏感信息拦截、同意、有效期、替代/删除、Mem0 HTTP 适配器、设备归属、幂等写工具、工单时间线 | `/memories`、`/tickets`、`packages/context/memory.py` |
| P4 | 正向反馈生成候选技能、静态检查、回归门禁、人工审批、版本、灰度、停用、回滚、运行时注入、100 任务技能矩阵 | `/feedback`、`/skills`、`/evals/skill-matrix` |
| P5 | 50 条冒烟集、400 条唯一盲测集、100 条技能任务、R0-R5/M0-M3、类别/安全/时延指标、Badcase、可靠 Worker、浏览器 E2E | `/evals/run`、`/evals/matrix`、`configs/experiments.yaml` |

## 数据规模

`data/synthetic/manifest.json` 固定记录 4 个产品族、8 个型号、24 个固件版本、72 份文档、400 条 FAQ、1000 条工单、20 个用户、200 条记忆、400 条正式用例、400 条冻结盲测用例、50 条冒烟用例和 100 条技能任务。运行 `python scripts/generate_synthetic_data.py` 可完全重建。

## 外部配置项

以下模型与观测能力启用时仍需外部资源：

- Ollama 模型权重：设置 `LLM_PROVIDER=ollama` 和模型名。
- BGE/Cross-Encoder 权重：安装 `.[local-embedding]`，切换配置后重新索引。
- Langfuse：提供可访问的 Langfuse v4 服务地址与密钥，然后设置 `LANGFUSE_ENABLED=true`。

企业 CRM 不是当前项目的依赖或验收缺项。`TicketTools` 已使用本项目数据库完成创建、幂等、确认门禁、状态查询和时间线闭环；只有未来明确选定第三方工单系统时，才需要在保持 `ToolResult` 契约的前提下增加适配器。

LightRAG 与 OpenViking 是研究对照组而非默认生产链路；适配器会在服务未配置时明确失败，不会伪装成本地混合检索结果。Docker 虚拟机实机验收状态和最终盲测结果记录在 `docs/final-verification.md`。

退款、换货、拆机、高压操作和真实硬件控制始终属于人工审批边界，不应改成无人值守自动执行。
