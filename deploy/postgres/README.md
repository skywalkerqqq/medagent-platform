# PostgreSQL 迁移计划（下一阶段，当前未接线）

> 现状：应用使用 SQLite（`server/db.py`，`?` 占位、`lastrowid`、AUTOINCREMENT、PRAGMA）。
> `deploy/docker-compose.yml` 的 `postgres` 仅是迁移演练位，**应用未连接**，不要把它当生产存储。

## 迁移步骤

1. **Schema 转换**：按 `server/db.py` 的 30+ 表生成 PG DDL（`SERIAL/BIGSERIAL`、`JSONB`、`TIMESTAMPTZ`、索引/外键）；
2. **数据访问层抽象**：把各模块 SQL 的 `?` → `%s`、`lastrowid` → `RETURNING id`、SQLite 函数替换；建议引入 repository 层，避免逐文件散改；
3. **双写/回放校验**：SQLite 导出 → PG 导入 → 对账（行数、金额、审计链、知识版本）；
4. **切换**：只读验证 → 灰度写 → 回滚预案（保留 SQLite 只读副本）；
5. **解锁能力**：多 worker/多副本、连接池、只读副本、PG 备份/PITR。

## 验收标准

- 25 项 API 测试 + 3 真实上游 + 4 Dify + 4 通知在 PG 下全部通过；
- 迁移前后关键数据逐表对账一致；
- 压测：目标 QPS / P95 / 错误率达标；
- 回滚演练通过（恢复 SQLite + 旧镜像）。

## 不在本阶段做

- 不引入 ORM 大改业务逻辑（先保持 handler 行为不变）；
- 不删除 SQLite 支持（本地开发/演示继续零依赖运行）。
