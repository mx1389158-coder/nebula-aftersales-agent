# V2 双后端最终验收记录

验收日期：2026-11-04

验收环境：Windows 11 + VirtualBox Ubuntu + Docker Compose，Java 21、Python 3.11、Node 22、PostgreSQL 16/pgvector、Redis 7。

## 验收结论

Java + Python 双后端主闭环已通过实际容器验收。Java 是用户、设备和工单的权威业务端；Python Agent 转发当前用户 JWT，在用户确认后调用 Java 创建工单。Nginx 同时代理 `/api/business/*` 与 `/api/ai/*`。

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
- 使用相同幂等键和相同请求体再次调用 Java，返回同一工单且 `deduplicated=true`。
- `biz` schema 所有者为 `aftersales_biz`，`ai` schema 所有者为 `aftersales_ai`；两个应用角色均无对方 schema 的 `USAGE` 权限。
- 验收后记录数为 `biz.tickets=1`、兼容表 `ai.tickets=0`，证明 V2 工单没有写入 Python 数据域。

## 自动化回归

| 范围 | 结果 |
| --- | --- |
| Java Maven/JUnit | 7 passed |
| Python Pytest | 38 passed |
| Ruff | passed |
| MyPy | passed |
| Vue Vitest | 2 passed |
| Vue TypeScript + Vite production build | passed |
| Docker Compose 配置 | passed |
| V2 黑盒跨服务闭环 | passed |

## 模型说明

本次双后端容器验收在隔离 VM 中临时覆盖为 `LLM_PROVIDER=mock`、`EMBEDDING_PROVIDER=hash`，因为 VM 不共享 Windows 上已下载的 Ollama/BGE 模型缓存且无法访问 Hugging Face。该覆盖没有修改项目 `.env`；模型切换、知识向量重建与评测属于此前已完成的独立模型验收，不影响本次 Java/Python 业务边界结论。

LightRAG/OpenViking 仍是可选外部研究对照组，需要项目方提供服务地址；默认 `hybrid` 生产闭环不依赖它们。
