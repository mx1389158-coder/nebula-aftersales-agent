# 部署与运维手册

## 本地开发

复制 `.env.example` 为 `.env`，安装 Python/Node 依赖，执行 Alembic 迁移，然后分别启动 API、Worker 和 Web。演示模式只允许本机使用，默认账号为 `demo@example.com`，密码 `demo-change-me`。

## Docker 开发部署

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 api worker
```

容器端口只绑定 `127.0.0.1`。宿主机 Ollama 通过 `host.docker.internal:11434` 访问；若启用 Compose 内 Ollama，设置 `COMPOSE_OLLAMA_BASE_URL=http://ollama:11434` 并使用 `--profile local-model`。

## 生产部署

生产变量至少包括：随机 `SECRET_KEY`、强 `POSTGRES_PASSWORD` / `BIZ_DB_PASSWORD` / `AI_DB_PASSWORD`、明确的 `CORS_ORIGINS`，以及随机且不入库的 `BUSINESS_SERVICE_CREDENTIAL`。后者只用于 `/auth/service-token` 换取短期服务 JWT；本地为空时该接口拒绝所有签发请求，生产 Compose 则在缺失或空值时直接拒绝启动。首次空库可临时配置 `BOOTSTRAP_ADMIN_EMAIL` 和不少于 12 位的 `BOOTSTRAP_ADMIN_PASSWORD`，登录后应移除这两个变量并轮换密码。

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

生产覆盖会启用 `ENVIRONMENT=production`、关闭演示模式并强制 PostgreSQL。应用启动前自动执行 `alembic upgrade head`。不得把 `.env`、模型缓存或数据库文件提交到 Git。

## 验证和回滚

1. 检查 `/api/v1/health`、Web 登录、聊天引用、记忆编辑与确认后建单。
2. 检查 Worker 心跳、失败重试和死信列表。
3. 发布前执行单测、浏览器 E2E、依赖审计和固定盲测。
4. 应用回滚使用上一镜像；数据库只允许使用已审阅的 Alembic downgrade。知识版本通过文档回滚 API 恢复，不能直接改表。

## 备份

每天对 PostgreSQL 做 `pg_dump`，同时备份 `job_data`；Redis 仅承担唤醒与限流，不作为唯一业务存储。每季度执行一次异机恢复演练，并记录恢复点目标与耗时。
