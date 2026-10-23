# 参考实现映射

所有上游仓库位于项目同级的 `reference-projects/`，仅作架构和接口研究。

| 参考项目 | 采用的思想 | 本项目实现位置 |
| --- | --- | --- |
| FastAPI full-stack template | 配置集中化、数据库依赖、API 分层、容器化 | `apps/api/app/core`、`apps/api/app/api` |
| Mem0 | Memory CRUD、身份字段不能由任意 metadata 覆盖、Provider 可替换 | `packages/context/memory.py`、`memories` 表 |
| OpenViking | resource / memory / skill 三类上下文边界、Retriever 适配器思路 | `packages/context`、`skills` 表与路由 |
| LightRAG | 结构感知递归分块、图检索作为对照而非默认主链 | `packages/context/chunking.py`、评测配置 |
| pgvector | PostgreSQL vector 类型、余弦距离、HNSW 索引 | `models.Chunk.embedding`、初始迁移 |
| Langfuse | request/trace/span、Prompt 与评测版本关联 | 消息 `trace_id`、LangGraph 节点 trace、评测 run |
| create-vue | Vue 3 + TypeScript + Vite 工程约定 | `apps/web` |

## 未直接绑定上游产品代码的原因

版本过滤、租户隔离、记忆删除、写操作确认和幂等是本项目业务约束，必须在自身测试中可验证。上游项目通过 Provider/Adapter 接入后，也不能绕过这些边界。

