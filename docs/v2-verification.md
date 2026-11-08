# V2 双后端最终验收记录

验收日期：2026-11-04

验收环境：Windows 11 + VirtualBox Ubuntu + Docker Compose，Java 21、Python 3.11、Node 22、PostgreSQL 16/pgvector、Redis 7。

## 验收结论

Java + Python 双后端主闭环已通过实际容器验收。Java 是用户、产品、设备、工单和审计的权威业务端；Python Agent 转发当前用户 JWT，在用户确认后调用 Java 创建工单。Nginx 同时代理 `/api/business/*` 与 `/api/ai/*`，用户、售后和管理员三角色浏览器闭环也已通过。

验证脚本：

```powershell
python scripts/verify_v2_stack.py
```

实际输出：

```text
V2_STACK_OK
health=business,ai; routing=nginx; auth=jwt; agent=confirm/resume
ownership=device; ticket=java-authoritative; idempotency=deduplicated
```

## 已通过项目

- 六个服务成功启动：PostgreSQL、Redis、Java Business、Python AI、Worker、Vue/Nginx；有健康检查的四个基础/API 服务均为 healthy。
- 通过 Nginx 调用 Java 登录，获得 Java 签发且 Python 可验证的 JWT。
- 使用同一 JWT 经 Java 查询当前用户设备，资源归属校验生效。
- 调用 Python Agent 创建工单时先返回 `need_confirm` 和持久化 pending action。
- 调用 `/api/ai/v1/chat/{thread_id}/resume` 确认后，Python 转发用户 JWT、请求 ID 和幂等键到 Java。
- Java 在单一事务内写入工单、状态事件、幂等记录和审计日志，Agent 返回真实工单 ID。
- 使用幂等键查询 Java 的对账接口，返回同一工单且 `deduplicated=true`；同键异载荷 POST 会返回 409，避免错误复用。
- 产品目录中的 PostgreSQL `jsonb` 型号聚合已规范化为 JSON 数组，设备型号、固件选择和绑定在浏览器中实测通过。
- Python 用户投影可恢复多个首次请求的并发插入冲突；退出账号同时清除本地会话 ID，禁止跨账号恢复会话。
- Playwright 完成普通用户问答、历史会话、设备绑定、记忆、建单，售后接单以及管理员用户/审计查看；录像见 `docs/demo/critical-flow-e2e.webm`。
- `biz` schema 所有者为 `aftersales_biz`，`ai` schema 所有者为 `aftersales_ai`；两个应用角色均无对方 schema 的 `USAGE` 权限。
- 黑盒验收中的工单只写入 `biz.tickets`，没有写入 Python 兼容工单表，证明业务写入边界生效。

## 自动化回归

| 范围 | 结果 |
| --- | --- |
| Java Maven/JUnit + Testcontainers PostgreSQL | 13 passed，0 skipped |
| Python Pytest | 40 passed |
| Ruff | passed |
| MyPy | passed |
| Vue Vitest | 3 passed |
| Vue TypeScript + Vite production build | passed |
| Docker Compose 配置 | passed |
| V2 黑盒跨服务闭环 | passed |
| Playwright 三角色完整栈 E2E | 1 passed |
| Ollama + BGE 50 条真实模型评测 | passed，Badcase=0 |

## 模型说明

本次双后端容器验收在隔离 VM 中临时覆盖为 `LLM_PROVIDER=mock`、`EMBEDDING_PROVIDER=hash`，使业务边界与浏览器流程可重复执行。该覆盖没有修改项目 `.env`；Windows 本机另行使用 Ollama `qwen2.5:1.5b` 与 `BAAI/bge-small-zh-v1.5` 完成了 50 条真实模型评测，任务成功率和决策准确率均为 1.0、Badcase 为 0，详见 `docs/model-evaluation-v2.md`。

LightRAG/OpenViking 仍是可选外部研究对照组，需要项目方提供服务地址；默认 `hybrid` 生产闭环不依赖它们。
