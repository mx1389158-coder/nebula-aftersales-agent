# 最终验证记录

验收整理日期：2026-10-27。所有观测与评测输入均为虚构数据。

## Ollama/BGE 冻结盲测

| 项目 | 结果 |
| --- | --- |
| 数据集 | `aftersales-blind-v3`，400 条唯一问题 |
| Git 提交 | `2b983056fa2b75382281713397db1bd7dfc03ecf` |
| 数据集 SHA256 | `820dbbfc14bd58ff83e66922a19a706845528ba563ebe79c330b760a052147a7` |
| 配置 | `hybrid_rerank + M3 + reviewed` |
| 模型 | Ollama `qwen2.5:1.5b` + BGE |
| 随机种子 | 42 |
| 硬件 | Windows CPU 环境 |
| 任务成功率 / 决策准确率 | 100% / 100% |
| 引用精度 / Recall@K / MRR / NDCG@K | 95.63% / 84% / 84% / 84% |
| 工具准确率 / 危险动作率 | 100% / 0% |
| p95 | 4210.15 ms |
| Badcase | 0 |

8 个类别均为 100% 任务成功率：单文档 100、跨文档 60、版本冲突 50、证据不足 40、记忆依赖 30、提示注入 20、安全转接 50、工具确认 50。首轮和二轮盲测分别暴露了记忆编号排序、同义意图路由与生成长尾问题；修复后使用全新措辞的 v3 终验，没有在已查看结果的数据集上重复刷分。

## 消融与技能矩阵

矩阵使用 BGE + 固定证据模板，以隔离被测变量；生产模型质量以上述 Ollama 盲测为准。

| 组合 | 数据集 | 成功率 | p95 ms |
| --- | --- | ---: | ---: |
| R0 no retrieval + M3 | smoke 50 | 48% | 268.07 |
| R1 dense + M3 | smoke 50 | 100% | 244.86 |
| R2 hybrid + M3 | smoke 50 | 100% | 257.16 |
| R3 hybrid rerank + M3 | smoke 50 | 100% | 519.77 |
| hybrid + M0 | smoke 50 | 88% | 14.80 |
| hybrid + M1 | smoke 50 | 88% | 15.56 |
| hybrid + M2 | smoke 50 | 88% | 457.89 |
| hybrid + M3 | smoke 50 | 100% | 257.16 |

100 条技能任务中：无技能、人工技能、抽取技能的任务成功率均为 100%；技能命中率分别为 0%、100%、100%。运行脚本为 `scripts/run_acceptance_matrix.py`，完整机器报告位于被忽略的 `data/jobs/acceptance-matrix.json`。

R4 LightRAG 和 R5 OpenViking 的适配器、失败封闭行为和单元测试已完成，但外部服务 URL 未配置，因此没有伪造这两组运行结果。两项需要可访问服务后使用 `--include-external` 执行。

## 工程验证

- 后端：Ruff、MyPy、35 个 Pytest 测试通过；覆盖率在最后一次完整统计中为 78%。
- 前端：Vitest 2 个测试、生产构建和 npm 高危依赖审计通过，0 个已知漏洞。
- 浏览器：Playwright 真实登录后完成聊天引用、记忆治理和确认建单，1/1 通过；视频为 `docs/demo/critical-flow-e2e.webm`。
- Langfuse：日本区客户端初始化成功，`release-verification` 合成 trace 已 flush；真实客户数据仍禁止跨境发送。
- 数据：72 文档、24 固件、400 正式集、400×3 盲测版本、50 冒烟和 100 技能任务可确定性重建。

## Docker Compose 实机验证

2026-10-27 在 VirtualBox `cpu-eval` 验证机上完成了全新数据卷部署。验证机为 Linux 6.8.0-147，Docker Server 29.1.3，Compose 2.40.3；应用源代码快照为 `354af55`，Docker 构建修复提交至 `75db4d5`。

| 检查项 | 结果 |
| --- | --- |
| Compose 配置与镜像构建 | 通过；API、worker 使用 `torch 2.14.1+cpu`，CUDA 为 `None` |
| 容器状态 | PostgreSQL、Redis、API healthy；worker、Web running |
| PostgreSQL | pgvector 0.8.7；Alembic `20261024_password_auth (head)` |
| 种子知识库 | 72 文档、216 分块 |
| Windows 到虚拟机端口 | `127.0.0.1:8000` 与 `127.0.0.1:5173` 可访问；Web HTTP 200 |
| API 冒烟 | health `ok`、数据库 `ok`、真实登录成功 |
| 问答闭环 | `ANSWER`，6 条引用，3 个决策轨迹步骤 |
| Docker worker 评测 | 50/50 成功，决策/引用/工具准确率均 100%，危险动作率 0，p95 15.55 ms |

首次实机构建同时修复了三项部署问题：Linux 默认解析 CUDA 版 PyTorch、弱网下载无法恢复、VirtualBox NAT 无法访问仅绑定 guest 回环地址。现在 CPU wheel 使用 PyTorch 官方索引，普通依赖支持 `PIP_INDEX_URL` 镜像、下载缓存和三轮重试；`COMPOSE_BIND_HOST` 默认仍为 `127.0.0.1`，只有虚拟机转发场景才显式改为 `0.0.0.0`。

为排除旧测试卷密码干扰，验收前仅删除并重建了 `aftersales-agent_job_data`、`aftersales-agent_postgres_data`、`aftersales-agent_redis_data` 三个验证用卷。当前完整 Compose 栈保留运行，供本机继续验收。

## 尚需外部环境完成的可选对照项

LightRAG/OpenViking 服务端未配置。它们是研究对照组，不影响默认 hybrid 生产闭环；若验收要求 R4/R5 实测，必须先提供或启动这两个服务。适配器、失败封闭行为和测试已经完成，不会把本地 hybrid 结果伪装成外部基线。

企业 CRM 不是缺项；当前项目数据库已完成带确认、幂等和时间线的工单闭环。
