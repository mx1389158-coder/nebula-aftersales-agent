# ADR-0003：采用数据库持久化的 Agent 中断协议

状态：已接受（2026-11-04）

## 背景

创建工单、保存长期记忆等操作必须先展示准确摘要，再由同一租户、同一用户明确确认。服务还必须支持进程重启、浏览器断线、多实例部署和重复提交，不允许只依赖进程内暂停对象。

## 决策

运行时仍使用 LangGraph `StateGraph` 编排节点，但中断状态通过 `agent_checkpoints` 表持久化，而不直接暴露 LangGraph 进程内 `interrupt()` 对象：

- 以 `(tenant_id, user_id, thread_id)` 唯一定位断点；
- `pending_action` 只保存经过约束的操作参数，不保存令牌或敏感信息；
- `/chat/{thread_id}/resume` 重新校验当前 JWT 与资源归属；
- `/chat/{thread_id}/cancel` 清空待执行操作，并将会话/断点标记为 cancelled；
- 写工具仍使用数据库幂等键；HTTP 超时后按同一幂等键查询结果，不盲目重放；
- 图执行设置 `recursion_limit`，所有恢复和取消均可审计、可测试。

## 原因

该协议把“暂停/恢复语义”与单个 Python 进程解耦，适合当前 FastAPI 多实例和滚动发布架构。它与 LangGraph 原生中断的用户体验一致，但将恢复依据放入本项目可迁移、可约束的数据库中，避免框架检查点格式升级影响业务数据。

## 后果

需要维护少量恢复路由与状态机测试；如果未来采用 LangGraph 官方数据库 Checkpointer，必须先提供旧 `agent_checkpoints` 数据迁移和幂等回归报告，不能直接替换线上协议。
