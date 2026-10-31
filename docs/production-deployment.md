# 生产化部署（Stage 1）

> 目标：把 POC 推进到“可容器化部署、可健康检查、可备份、有 TLS 入口”的第一阶段。
> **如实说明：业务存储仍是 SQLite（持久化卷），FastAPI 只是 HTTP 边缘；PostgreSQL/HA/等保尚未完成。**

## 一、当前边界

| 项 | 状态 | 说明 |
|---|---|---|
| FastAPI + Uvicorn 边缘 | ✅ | `production/app.py` 复用 `server/handlers.py`；单 worker |
| 容器镜像 | ✅ | `deploy/Dockerfile`，非 root 用户、健康检查 |
| Docker Compose | ✅ | `deploy/docker-compose.yml`：app + 可选 TLS 代理 |
| 健康检查 | ✅ | `/healthz` 存活、`/readyz` 数据库就绪 |
| 安全响应头 | ✅ | nosniff / DENY / no-referrer / X-Request-Id / X-Process-Time |
| 审计哈希链 | ✅ | `/api/audit/verify`；WORM/异地仍待等保阶段 |
| 备份脚本 | ✅ | `deploy/backup.ps1`、`deploy/backup.sh`（SQLite online backup + SHA256） |
| TLS 反代模板 | 🟡 | `deploy/nginx`，需院方证书；未启用 HTTP/2 优化与 WAF |
| PostgreSQL | 🟡 | 迁移工具 `production/migrate_to_pg.py`（导出/DDL/导入/对账）已就绪；**运行时未接线 PG** |
| SSO / 等保 / WAF / 限流 | ⬜ | 未实现 |
| HA / 多副本 / 压测 | ⬜ | SQLite 单写限制，需先迁移 PG |

## 二、目录

```
production/app.py        FastAPI 边缘（业务复用 server/handlers.py）
production/requirements.txt
deploy/Dockerfile
deploy/docker-compose.yml
deploy/nginx/nginx.conf  TLS + 反代模板
deploy/backup.ps1|.sh    备份脚本
deploy/postgres/         PG 迁移计划（下一阶段）
```

## 三、启动

```powershell
cd medagent-platform

# 构建并启动（默认 8080 → 容器 8000；数据在命名卷 medagent-data）
docker compose -f deploy/docker-compose.yml up -d --build

# 健康检查
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz

# 查看日志/状态
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f app
```

无 Docker 时仍可零依赖运行：

```powershell
python server/app.py --port 8090 --db data/medagent.db --reset
```

## 四、配置（环境变量）

| 变量 | 必填 | 说明 |
|---|---|---|
| `MEDAGENT_DB` | 否 | SQLite 路径，默认 `/app/data/medagent.db` |
| `MEDAGENT_WEB` | 否 | 前端目录，默认 `/app/web` |
| `LLM_MODE=live` + `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` | 否 | 真实 OpenAI 兼容模型上游 |
| `DIFY_BASE_URL` / `DIFY_API_KEY` | 否 | Dify 长尾应用运行 |
| `ALERT_WEBHOOK_URL` | 否 | 企业微信/钉钉告警通知 |
| `WX_APPID` / `WX_SECRET` | 否 | 小程序真实 code2session |

> 密钥通过编排平台 Secret / KMS 注入，**不要写进镜像或 git**；`.env` 不提交。

## 五、TLS 反向代理（可选）

```powershell
# 1) 生成自签证书仅用于本地验证（生产换 CA 证书）
cd deploy/nginx/tls
openssl req -x509 -nodes -newkey rsa:2048 -days 365 -keyout server.key -out server.crt -subj "/CN=localhost"
cd ../..

# 2) 启动代理（https://127.0.0.1:8443）
docker compose -f deploy/docker-compose.yml --profile proxy up -d
```

生产必须：院方/公网 CA 证书、TLS1.2+、HSTS、限制证书目录权限 600、关闭示例自签证书。

## 六、备份与恢复

```powershell
# 备份（默认 data/medagent.db → data/backups/，并写 SHA256SUMS）
powershell -File deploy/backup.ps1

# 容器内备份（SQLite 在命名卷）
docker compose -f deploy/docker-compose.yml exec app python -c "import sqlite3; s=sqlite3.connect('/app/data/medagent.db'); d=sqlite3.connect('/app/data/backups/backup.db'); s.backup(d); d.close()"

# 恢复：停止 app → 用备份文件替换卷内 medagent.db → 启动 → /readyz 验证
```

要求：备份加密存储、异地保留、定期恢复演练；审计/病历相关留存在等保阶段进一步加固。

## 七、升级流程

1. 备份数据库并校验 SHA256；
2. `git pull` / 构建新镜像（固定 image tag）；
3. `docker compose up -d --build`；
4. 验证 `/healthz` `/readyz` + 关键接口冒烟（登录/试跑/报告）；
5. 失败回滚：切回上一镜像 tag + 恢复备份（SQLite 迁移脚本缺失时不可跨版本回退）。

## 八、下一阶段（按顺序）

1. **PostgreSQL 迁移**：迁移工具已就绪（见 `deploy/postgres/README.md`），下一步 repository 抽象与运行时切换；完成后可多副本 + 连接池；
2. **SSO/OIDC + 会话存储**（Redis），替代当前内存 Token；
3. **可观测性**：结构化日志、指标（Prometheus）、Trace、告警；
4. **安全**：限流、WAF、密钥管理、审计 WORM、等保测评；
5. **HA/容灾与压测**：多副本、只读副本、备份 RPO/RTO 验证；
6. **合规/临床**：注册资料、临床评价、真实 HIS/PACS 联调。

## 九、已知限制（必须写进上线评审）

- 单 worker + SQLite，不能水平扩展；并发写高时可能 `database is locked`；
- 无 SSO/MFA，Token 存储于内存（重启失效）；
- 无速率限制/WAF，公网暴露前必须加；
- 无结构化日志/指标，生产排障能力不足；
- 小程序/告警/Dify/模型上游需真实凭据与网络策略。
