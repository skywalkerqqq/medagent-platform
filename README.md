<div align="center">

# 🏥 MediAgent

**医疗 AI 中台 · POC 基线 v1.1**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)](#-测试)
[![Dependencies](https://img.shields.io/badge/core%20deps-zero-blue.svg)](#-快速开始)
[![Status](https://img.shields.io/badge/status-POC-orange.svg)](#-poc-边界诚实说明)
[![Docker](https://img.shields.io/badge/Docker-compose%20ready-2496ED?style=flat&logo=docker&logoColor=white)](deploy/docker-compose.yml)

**中文** | [English](README.en.md)

</div>

> 把「AI 应用能不能上临床」这件说不清的事，变成一条**可评测、可审批、可回滚、可追溯**的流水线。
> 应用工厂 → 知识治理 → 模型网关 → 评测门禁 → 双审批发布 → 患者端联动，全程留痕。

一个**零第三方依赖**即可跑起来的医疗 AI 中台 POC：Python 标准库 + SQLite 起服务，原生 ES Module 写前端，微信小程序做患者端。

> ⚠️ 这是 POC / 试点准备系统，不是生产或注册产品。真实边界见 [POC 边界](#-poc-边界诚实说明)。

---

## ✨ 核心能力

| 模块 | 能力 |
|---|---|
| 🔐 身份与权限 | 服务端 Token 会话（8h）、角色 × 科室 × 应用归属、审批职责分离；**拒绝 `X-User-Id` 作为身份** |
| 🏭 应用工厂 | 3 个模板（知识问答 / 病历质控 / 报告初稿）、创建配置、试跑（输出 + 引用 + 免责 + 版本 + 降级） |
| 💬 运行调试 | 对话式试跑、执行轨迹（模板→记忆→知识/规则→模型→安全）、👍/👎 反馈自动入 BadCase |
| 📚 知识中心 | 导入 / 审核 / 版本 / 生效失效 / 范围权限 + FAQ；过期与待审不参与检索；引用可核验 |
| 🔄 知识来源同步 | 文件 / JSON / URL 来源登记 → 增量同步为 pending → 审核后生效；路径限制在 `data/` 内 |
| 🧠 长期记忆 | 三级范围（user/agent/tenant）× 四类（preference/fact/summary/instruction）、去重、软删硬删、64 维向量检索、session/auto 写入 |
| 🔌 模型网关 | 模型注册、策略链、超时、显式降级标记、调用记录；上游不可用不伪造结果 |
| 📊 评测门禁 | 评测集、指标（召回/引用/答案正确/编造/检出）、阈值、未达标 409 阻断发布 |
| ✅ 双审批发布 | 科室 → 平台两级审批；发布生成不可变版本快照；支持停用与回滚 |
| 🩺 报告编辑器 | 草稿生成 → 医生编辑 → 签名 → 修改率统计 → 审计；已签名不可改 |
| 🔗 数据集成 | HIS / EMR / PACS **mock**：患者上下文聚合、签名报告回写（幂等 + 外部 ID + 审计） |
| 📱 患者小程序 | 微信登录 → 绑定 → 报告（仅批准可见）→ 随访 → 危险信号转人工；患者数据按绑定隔离 |
| 🚨 医疗 AI 安全 | 禁止输出（诊断/处方/不安全建议）自动阻断 + 安全事件 + 转人工；模型故障降级不伪造 |
| 🧾 审计哈希链 | 每条审计 SHA-256 链式哈希（prev_hash），`/api/audit/verify` 检测篡改与断链 |
| 📈 运营看板 | 10 项指标（口径 + 来源 + 当前值）、成本对账、企业微信/钉钉告警通知 |
| 🐳 生产化 Stage 1 | FastAPI 边缘 + Docker/Compose + `/healthz` `/readyz` + 安全响应头 + 令牌桶限流 + 备份脚本 + TLS 反代模板 |

---

## 📸 界面

| 登录 | 总览 / 验收 |
|---|---|
| ![登录](screenshots/00-login.png) | ![总览](screenshots/01-dashboard.png) |

| 应用工厂 | 应用详情（门禁 + 审批） |
|---|---|
| ![应用工厂](screenshots/02-app-factory.png) | ![应用详情](screenshots/03-app-detail.png) |

| 运行调试（对话 + 轨迹） | 模型网关 |
|---|---|
| ![运行调试](screenshots/09-playground.png) | ![模型网关](screenshots/05-model-gateway.png) |

| 运营 / BadCase | 知识中心 |
|---|---|
| ![运营](screenshots/06-ops.png) | ![知识](screenshots/07-knowledge.png) |

| 长期记忆（三级范围 / 注入） | 患者端（小程序联动） |
|---|---|
| ![记忆](screenshots/10-memory.png) | ![患者端](screenshots/08-patient.png) |

| 报告编辑器（草稿 → 签名） | 数据集成（HIS/EMR/PACS mock） |
|---|---|
| ![报告编辑](screenshots/11-report.png) | ![数据集成](screenshots/12-integrations.png) |

---

## 🚀 快速开始

环境：**Python 3.12+**，核心零第三方依赖。

```bash
cd medagent-platform
python server/app.py --port 8090 --db data/medagent.db --reset
# 打开 http://127.0.0.1:8090
```

首次启动自动建库并写入合成种子数据（32 张表 / 8 个账号 / 3 个模板 / 6 条知识 + 4 条 FAQ / 3 个应用 / 2 个患者）。

Windows 可用 `scripts/start.ps1`，Linux/macOS 可用 `scripts/start.sh`。

### 👤 演示账号

密码统一为 `medagent123`。

| 账号 | 角色 | 用途 |
|---|---|---|
| `u_creator` | 业务人员 | 从模板建应用、试跑、提交发布 |
| `u_dept` | 科室审批人 | 科室级审批（本部门） |
| `u_platform` | 平台审批人 | 平台审批、发布、回滚、停用 |
| `u_knowledge` | 知识运营 | 知识导入 / 审核 |
| `u_eval` | 评测人员 | 执行评测、看门禁 |
| `u_doctor` | 医生 | 试跑、临床复核、报告编辑签名 |
| `u_patient` | 患者 | 患者端（绑定 / 报告 / 随访） |
| `u_admin` | 平台管理员 | 全量治理、模型开关、审计导出 |

### 🧪 测试

```bash
python tests/test_api.py               # 25 项接口验收（真实进程 + HTTP）
python tests/test_llm_live.py          # 3 项真实模型上游（fake OpenAI 兼容上游）
python tests/test_dify.py              # 4 项 Dify 适配（fake Dify）
python tests/test_notify.py            # 4 项告警通知（fake webhook）
python tests/test_rate_limit.py        # 2 项令牌桶限流
python tests/test_pg_compat.py         # 7 项 PG 运行时转换（1 项真实 PG 跳过）
python tests/test_pg_migration.py      # 3 项 SQLite→PG 迁移与对账
python tests/test_production_import.py # 2 项 FastAPI 边缘导入（无 fastapi 时跳过）
```

共 **50 项**，全部通过。或用 `scripts/check.sh` / `scripts/check.ps1`（测试 + 前端 JS 语法）。

### 🐳 容器化

```bash
docker compose -f deploy/docker-compose.yml up -d --build
curl http://127.0.0.1:8080/healthz   # {"status":"ok",...}
curl http://127.0.0.1:8080/readyz    # {"status":"ready","db":"sqlite"}
```

单 worker + SQLite 持久化卷；水平扩展须先完成 PostgreSQL 迁移。详见 [生产化部署](docs/production-deployment.md)。

---

## 🏗 架构

```
浏览器（原生 ES Module SPA，无构建）
        │  JSON / Bearer Token（不接受 X-User-Id）
        ▼
server/app.py（零依赖 HTTP：静态托管 + API 路由 + Token 中间件）
  ├─ auth.py              登录 / 会话 / 权限
  ├─ templates.py         3 个 POC 模板（提示词 / 配置 / 阈值）
  ├─ apps.py              应用工厂、试跑、发布检查、双审批、发布 / 回滚 / 停用
  ├─ knowledge.py         知识导入 / 审核 / 版本 / 生效失效 / 检索引用
  ├─ knowledge_sources.py 来源登记与增量同步（file/json/url）
  ├─ models.py            模型注册、策略链、降级、调用记录
  ├─ eval_center.py       评测集、指标、门禁、结果
  ├─ memory.py            长期记忆（三级范围 / 去重 / 向量检索 / 试跑注入）
  ├─ engine.py            生成引擎（模板 + 检索 + 安全 + 网关）
  ├─ safety.py            禁止输出、风险阻断、人工接管
  ├─ reports.py           报告草稿 / 编辑 / 签名 / 修改率
  ├─ integrations.py      HIS/EMR/PACS mock 与报告回写
  ├─ dify_adapter.py      Dify 应用登记与 blocking 调用
  ├─ ops.py               指标口径、BadCase、审计哈希链
  ├─ patient.py           患者绑定 / 授权 / 报告 / 随访 / 转人工
  ├─ wechat.py            微信登录（真实 jscode2session / dev mock）
  ├─ ratelimit.py         令牌桶限流（429 + Retry-After）
  ├─ pg_compat.py         PG 运行时兼容层（实验性）
  └─ seed.py              合成种子数据
production/               FastAPI 生产边缘（复用 server/handlers.py）
deploy/                   Dockerfile、Compose、TLS 反代、备份脚本、PG 迁移计划
web/                      index.html + app.css + app.js（无构建）
miniprogram/              患者服务小程序（导入微信开发者工具即可）
tests/                    50 项测试（真实进程 / fake 上游）
docs/                     接口契约、需求映射、生产部署、压测基线
```

**技术栈**：Python 标准库（`http.server`、`sqlite3`、`hashlib`）+ 原生 ES Module + WXML/WXSS。
**存储**：SQLite，32 张表；FastAPI/Uvicorn 仅用于生产边缘，迁移工具可选 `psycopg`。

---

## 🔍 关键流程

**1. 创建并发布应用**

```
u_creator 建应用(草稿) → 试跑(输出+引用+免责+版本+降级)
   → 提交发布 → 自动检查(模板/知识范围/可用知识/评测门禁/高风险安全事件)
   → 未通过 409 release_blocked(逐项原因)
   → 科室审批 → 平台审批 → 不可变版本快照 → published
   → 支持停用 / 回滚(恢复配置且与展示版本一致)
```

**2. 知识治理**

```
导入(来源/版本/生效/失效/范围) → 待审核(不参与检索) → 审核通过(参与检索)
   → 过期自动退出检索；所有操作审计
```

**3. 患者端**

```
微信登录(dev mock) → 绑定(患者标识 + 核验码 654321) → 授权
   → 报告(仅 approved_for_patient=1) → 随访提交
   → 危险信号(胸痛/呼吸困难/出血) → 生成人工待办 + 就医提示
   → 支持撤回授权 / 解绑；患者数据按绑定隔离
```

**4. 模型故障安全**

```
策略链(private-llm → mock-fallback)
   → 主模型禁用时自动降级并显式标记 degraded
   → 全部不可用 → 拒绝生成确定性结论 + 转人工，不把 mock 当真实结果
```

---

## 📡 API 摘要

认证：除 `/api/health`、`/api/auth/login`、`/api/auth/wx-login` 外均需 `Authorization: Bearer <token>`。
错误格式：`{"error":{"code":"...","message":"...","details":[...]}}`，不返回堆栈。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录，返回 Bearer Token |
| POST | `/api/auth/wx-login` | 微信登录（真实 / mock） |
| GET/POST | `/api/apps` | 应用列表 / 创建 |
| POST | `/api/apps/{id}/trial` | 试跑（输出 / 引用 / 版本 / 轨迹 / 自动记忆） |
| POST | `/api/apps/{id}/feedback` | 反馈（无用 → BadCase） |
| GET | `/api/apps/{id}/release-check` | 发布前逐项检查 |
| POST | `/api/apps/{id}/submit` | 提交发布（进入科室审批） |
| POST | `/api/approvals/{id}/decide` | 审批通过 / 拒绝（科室 → 平台） |
| GET/POST | `/api/knowledge`、`/api/faqs` | 知识 / FAQ 列表与导入 |
| GET | `/api/knowledge/search?q=` | 检索（仅生效 + 已审核 + 范围内） |
| GET/POST | `/api/knowledge/sources` | 知识来源登记 / 同步 |
| GET/POST | `/api/memories` | 记忆列表 / 新建 |
| GET | `/api/memories/search?q=&mode=vector` | 64 维向量 / 关键词检索 |
| POST | `/api/eval/run` | 执行评测（门禁判定） |
| GET | `/api/ops/metrics`、`/api/ops/costs?days=30` | 指标口径 / 成本对账 |
| GET | `/api/audit`、`/api/audit/verify` | 审计查询 / 哈希链校验 |
| POST | `/api/integrations/report-writeback` | 签名报告回写 HIS（幂等） |
| GET/POST | `/api/patient/*` | 绑定 / 报告 / 随访 |

完整契约见 [`docs/api-contract.md`](docs/api-contract.md)。

---

## ⚠️ POC 边界（诚实说明）

这是 **POC / 试点准备** 系统，**不是生产或注册产品**：

- 🧪 AI 输出由模板 / 规则 + 模拟模型生成，**非真实临床模型**，不用于任何诊疗决策；
- 🚫 未实现：真实 Dify / RAGFlow 部署、真实 HIS/EMR/PACS 接口、TLS/等保测评、KMS、PostgreSQL 生产运行、K8s、SSO/MFA、真实临床验证；
- 💬 微信登录默认 **dev mock**，真实需配置 `WX_APPID` / `WX_SECRET`；
- 🗂 所有数据均为**合成种子数据**，不含真实患者信息；
- 🐘 PG 运行时兼容层为**实验性**，未在真实 PostgreSQL 验证；PG 迁移工具已完成但运行时未接线；
- 📉 单 worker + SQLite，不能水平扩展；压测基线仅为本机只读接口，不是容量承诺。

---

## 🔒 安全与合规

- **认证**：服务端签发 Token（8h），不信任 `X-User-Id`；登录 / 退出 / 权限校验全在服务端；
- **权限**：角色 + 科室 + 应用归属 + 审批职责分离；
- **数据**：患者数据按绑定隔离，报告仅批准可见，患者标识最小化；
- **审计**：关键操作 SHA-256 哈希链留痕，导出需权限且留痕；
- **安全**：禁止输出自动阻断并转人工；模型不可用不伪造结果；错误不回堆栈；
- **密钥**：仅从环境变量 / Secret 注入，`.env` 不提交，镜像内不含凭据。

生产部署前的必读限制见 [生产化部署 · 已知限制](docs/production-deployment.md)。

---

## 📚 文档

| 文档 | 内容 |
|---|---|
| [`docs/api-contract.md`](docs/api-contract.md) | 接口、错误码、认证与安全约定 |
| [`docs/requirements-mapping.md`](docs/requirements-mapping.md) | v1.1 FR / NFR / TBD 与实现映射（含未实现项） |
| [`docs/prd-execution-status.md`](docs/prd-execution-status.md) | 模块执行状态与下一步 |
| [`docs/production-deployment.md`](docs/production-deployment.md) | 部署、备份、TLS、边界与下一阶段 |
| [`docs/postgres-runtime-switch.md`](docs/postgres-runtime-switch.md) | PG 运行时切换（实验性） |
| [`docs/load-test-baseline.md`](docs/load-test-baseline.md) | 本机压测基线与局限 |
| [`deploy/postgres/README.md`](deploy/postgres/README.md) | SQLite → PostgreSQL 迁移工具 |
| [`miniprogram/README.md`](miniprogram/README.md) | 患者端小程序导入与联调 |

---

## 📄 License

[MIT](LICENSE) © skywalkerqqq
