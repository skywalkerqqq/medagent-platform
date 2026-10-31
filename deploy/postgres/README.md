# PostgreSQL 迁移（Stage 2 准备：工具已就绪，运行时未接线）

> 现状：应用仍使用 SQLite（`server/db.py`，`?` 占位、`lastrowid`、AUTOINCREMENT、PRAGMA）。
> 本目录的工具已完成 **导出/DDL/导入/对账**；**应用运行时尚未连接 PG**，不要切生产流量。
> `deploy/docker-compose.yml` 的 `postgres` 仅为迁移演练位。

## 工具

`production/migrate_to_pg.py`

```text
--db PATH        SQLite 路径（默认 data/medagent.db）
--out DIR        导出目录（dump.json / schema.sql / manifest.json）
--pg-url URL     目标 PG（postgresql://user:pass@host:5432/db）
--import         导入 PG（会先 DROP 同名表，仅演练）
--verify         对账行数与内容校验和
```

## 1. 导出与生成 DDL（不需要 PG）

```powershell
python production/migrate_to_pg.py --db data/medagent.db --out data/migration
# 产物：
#   data/migration/dump.json     全表数据 + 每表 checksum
#   data/migration/schema.sql    PostgreSQL DDL（AUTOINCREMENT → BIGSERIAL 等）
#   data/migration/manifest.json 行数/表数/SHA256
```

**必须人工复核 `schema.sql`**：SQLite 类型/默认值/约束只是近似转换，索引名、保留字、布尔/JSON 字段需按 PG 调整。

## 2. 导入 PostgreSQL（演练）

```powershell
pip install -r production/requirements-migration.txt
docker compose -f deploy/docker-compose.yml --profile pg up -d postgres
$env:PG_URL="postgresql://medagent:<password>@127.0.0.1:5432/medagent"

python production/migrate_to_pg.py --db data/medagent.db --out data/migration --pg-url $env:PG_URL --import
python production/migrate_to_pg.py --db data/medagent.db --out data/migration --pg-url $env:PG_URL --verify
```

预期 `verify` 输出 `"ok": true`；若不一致，按表逐项排查（类型转换、默认值、时区）。

## 3. 运行时切换（尚未完成）

1. **Repository 抽象**：把各模块 SQL 收敛到存储接口（`?`→`%s`、`lastrowid`→`RETURNING id`、SQLite 函数替换）；
2. **双跑验证**：PG 只读旁路 + 关键接口回归（25 项 API + live/Dify/通知 + 迁移对账）；
3. **灰度/回滚**：保留 SQLite 只读副本，切换失败可回滚；
4. 切换后再启用多 worker/多副本、连接池、只读副本、PG PITR 备份。

## 验收标准

- 25 项 API + 3 真实上游 + 4 Dify + 4 通知在 PG 下全部通过；
- 迁移前后逐表行数/校验和一致；
- 压测目标 QPS/P95/错误率达标；
- 回滚演练通过。

## 不做

- 不在本阶段引入 ORM 重写业务逻辑；
- 不删除 SQLite 支持（本地零依赖开发/演示继续可用）。
