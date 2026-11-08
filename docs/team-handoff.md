# 项目交接速览

本文件用于帮助新成员快速理解“星云智家”售后智能体最终版本。更完整的实现清单见 `completion-checklist.md`，实机结果见 `v2-verification.md`，真实模型指标见 `model-evaluation-v2.md`。

## 系统结构

- `backend-java/`：Java 21 权威业务服务，负责登录、用户与角色、产品、固件、设备、工单、审计和幂等写入。
- `apps/api/`：Python FastAPI AI 服务，负责会话、LangGraph Agent、RAG、记忆、技能治理和评测接口。
- `apps/worker/`：文档处理及评测异步任务。
- `apps/web/`：Vue 3 + Pinia 前端，覆盖用户、售后和管理员三种角色。
- `packages/`：Agent、检索、记忆、工具和观测公共模块。
- `infra/`：Python 数据库迁移与部署配置。
- `backend-java/src/main/resources/db/migration/`：Java `biz` schema 的 Flyway 迁移。
- `evals/`、`data/`：评测定义、合成数据和可重建样例。
- `tests/`、`backend-java/src/test/`、`apps/web/e2e/`：Python、Java、前端和完整栈测试。

## 数据与调用边界

Java 是用户、产品、设备、工单和审计的唯一权威业务端。Python 不直接写 Java 的业务表；Agent 在用户确认后携带用户 JWT、Trace ID 和幂等键调用 Java。Python 独立管理会话、知识、记忆、技能和评测数据。

浏览器统一访问 Web/Nginx：

- `/api/business/v1/*` 转发至 Java。
- `/api/ai/v1/*` 转发至 Python。

## 最快启动方式

在项目根目录执行：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

打开 `http://127.0.0.1:5173`。演示账号：

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 用户 | `demo@example.com` | `demo-change-me` |
| 售后 | `support@example.com` | `support-change-me` |
| 管理员 | `admin@example.com` | `admin-change-me` |

真实模型运行需要本机 Ollama 模型与 BGE 权重；未准备模型时可使用 `docker-compose.test.yml` 的 mock/hash 测试覆盖。

## 验证入口

```powershell
# Python
.\.venv\Scripts\python.exe -m pytest -q

# Java
cd backend-java
mvn test

# 前端
cd ..\apps\web
npm test -- --run
npm run build

# 六服务完整栈 E2E（Windows）
npm run test:e2e:windows
```

最终验收结果：完整容器验收中的 Java 13 项和 Playwright 三角色 E2E 均通过；收尾后的 Python 49 项、Vue 4 项测试全部通过，并新增 Java 并发幂等与空服务凭据单测。Ollama + BGE 的 50 条生产配置评测 Badcase 为 0。

## 安全与交接说明

- 压缩包不包含 `.env`、Langfuse 密钥、模型权重、虚拟环境、依赖缓存或运行数据库。
- `.env.example` 只能作为模板；生产部署必须更换 JWT、数据库、服务身份和管理员密码。
- LightRAG/OpenViking 是可选外部研究对照组，不属于默认 hybrid 生产依赖。
- 退款、换货、拆机、高压操作和真实硬件控制必须保留人工审批。
