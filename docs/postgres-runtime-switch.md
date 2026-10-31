# 运行时 PostgreSQL 切换（Stage 2 · 实验性）

> 状态：**兼容层已实现，纯转换测试通过；尚未在真实 PG 实例上验证**。
> 默认仍使用 SQLite；`DATABASE_URL` 未设置时行为完全不变。
> 未经下面“验证清单”通过，禁止用于生产。

## 实现方式

`server/pg_compat.py`：SQLite 风格 SQL 的 psycopg 适配层（不是业务重写）：

| SQLite 用法 | PG 适配 |
|---|---|
| `?` 占位符 | 转换为 `%s`（跳过字符串字面量） |
| `INSERT ...` 后 `cursor.lastrowid` | 对 BIGSERIAL id 表自动追加 `RETURNING id` |
| `INSERT OR IGNORE` | `INSERT ... ON CONFLICT DO NOTHING` |
| `sqlite3.Row` 下标/列名 | `PGRow` 同时支持 `row[0]`、`row["col"]`、`dict(row)` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | 建表转换为 `BIGSERIAL PRIMARY KEY` |
| `REAL` / `DATETIME` | `DOUBLE PRECISION` / `TIMESTAMPTZ` |
| SQLite PRAGMA/WAL | PG 模式不执行 |

启用方式：

```powershell
$env:DATABASE_URL="postgresql://medagent:<password>@127.0.0.1:5432/medagent"
pip install -r production/requirements-migration.txt   # psycopg
python server/app.py --port 8090 --reset                 # 注意：--reset 会 DROP public schema！
```

生产化 FastAPI 边缘同样读取 `DATABASE_URL`（透传环境变量）。

## 已验证 / 未验证

| 项 | 状态 |
|---|---|
| 占位符转换（含字符串内 `?` 不转） | ✅ 单元测试 |
| `INSERT OR IGNORE` 转换 | ✅ |
| `RETURNING id` 生成 | ✅ |
| Schema 类型转换 | ✅ |
| `PGRow` 兼容 `sqlite3.Row` 用法 | ✅ |
| **真实 PG 连接 + 完整 API 回归** | ⬜ 本机无 PG/Docker，未执行 |
| 连接池/多副本 | ⬜ 每请求新建连接，性能不足 |
| 数据从 SQLite 迁移到 PG | 🟡 `production/migrate_to_pg.py` 已就绪 |
| 双跑对账（同一请求 SQLite/PG 结果一致） | ⬜ |

## 验证清单（必须在有 PG 的环境执行）

```powershell
# 1) 专用测试库（会被 DROP public schema，绝不能用生产库）
$env:PG_TEST_URL="postgresql://medagent:pass@127.0.0.1:5432/medagent_test"
$env:PG_TEST_ALLOW_RESET="1"
python tests/test_pg_compat.py     # 真实 PG 烟测（可选测试将执行）

# 2) 迁移工具导出/导入/对账
python production/migrate_to_pg.py --db data/medagent.db --out data/migration --pg-url $env:PG_TEST_URL --import
python production/migrate_to_pg.py --db data/medagent.db --out data/migration --pg-url $env:PG_TEST_URL --verify

# 3) 全量 API 回归（PG 模式）
$env:DATABASE_URL=$env:PG_TEST_URL
python tests/test_api.py
python tests/test_llm_live.py
python tests/test_dify.py
python tests/test_notify.py

# 4) 关键链路：登录/试跑/知识检索/报告签名/审计校验
# 5) 双跑对账与压测（RPO/RTO 另做）
```

## 已知风险

- **未在真实 PG 验证**：SQL 方言差异可能仍有遗漏（保留字、默认值、事务隔离、LIKE 大小写）；
- 每请求新建连接：高并发会耗尽 PG 连接，需 `psycopg_pool`；
- 无跨库一致性/双写：切换窗口需停写 + 迁移对账；
- `--reset` 会 `DROP SCHEMA public CASCADE`：仅限专用测试库；
- 审计哈希链逻辑不变，但 PG 下时间/排序需回归验证；
- SQLite 专有 `PRAGMA` 已跳过，`CREATE INDEX IF NOT EXISTS` 在 PG 可用。

## 下一步

1. 在有 PG 的环境跑上述清单，修复方言差异；
2. 引入连接池（psycopg_pool），移除 `--reset` 依赖；
3. 双跑对账 + 灰度切换；
4. 多副本/只读副本/备份 PITR；
5. 完成后更新 PRD 生产化状态为“PG 已验证”。
