# V2 Java + Python 双后端实现说明

## 责任边界

- Java 是用户、产品、设备、工单、状态事件、幂等记录和审计日志的唯一权威写入方。
- Python 保存会话、消息、知识、向量、记忆、Checkpoint、评测和后台任务。
- Agent 创建或查询工单时转发当前用户 JWT；Java 再做角色、租户和资源归属校验。
- PostgreSQL 单实例使用 `aftersales_biz/biz` 与 `aftersales_ai/ai` 两套账号和 Schema。两端没有跨域表写入权限。

## API 入口

| 路由 | 服务 | 说明 |
| --- | --- | --- |
| `/api/business/v1/*` | Spring Boot :8080 | 登录、用户、产品、设备、工单 |
| `/api/ai/v1/*` | FastAPI :8000 | 会话、RAG、知识、记忆、技能、评测 |

Java 登录签发 HS256 JWT。Java 与 Python 均验证 `iss=nebula-business-service`、`aud=nebula-platform`、签名和有效期。生产环境必须替换 `SECRET_KEY`；内部批处理可通过独立 `BUSINESS_SERVICE_TOKEN` 扩展服务身份，禁止借用管理员用户令牌。

## 工单一致性

创建工单必须发送 `Idempotency-Key`。Java 先用唯一约束原子预留幂等记录，再在同一事务写入工单、`ticket_events` 和 `audit_logs`；相同键、相同内容返回原资源，相同键、不同内容返回冲突。状态更新使用 `version` 条件更新实现乐观锁。

Agent 写操作流程为：生成摘要 → 持久化 pending action → 返回确认事件 → `POST /api/ai/v1/chat/{thread_id}/resume` → Java Tool → 清除 pending action。写请求超时时不会盲目自动重试。

## 运行模式

```powershell
# 日常开发（Mock LLM）
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# 固定 Mock 与哈希向量测试模式
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build

# Ollama + BGE 演示模式
docker compose -f docker-compose.yml -f docker-compose.demo.yml --profile local-model up --build
```

首次使用新的 `biz/ai` 数据域需要新 PostgreSQL 数据卷。升级已有 V1 数据时不要直接删除业务卷；应先备份，再执行单独的数据迁移方案。

## 验证命令

```powershell
docker compose config --quiet
docker compose build business api worker web
docker compose up -d postgres redis business api worker web
docker compose ps

# Java
docker compose run --rm business java -version

# Python / Frontend（宿主机开发环境）
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix apps/web test
npm.cmd --prefix apps/web run build
```

旧 `/api/v1` 仅在本地兼容开关 `ENABLE_LEGACY_API=true` 时启用；Compose 双后端模式默认关闭，避免绕开 Java 登录与业务边界。
