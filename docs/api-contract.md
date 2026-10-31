# MediAgent v1.1 API 契约（POC 基线）

- Base URL：`http://127.0.0.1:8090`（生产需 HTTPS）
- 认证：除 `/api/health`、`/api/auth/login`、`/api/auth/wx-login` 外，均需 `Authorization: Bearer <token>`；**不接受 `X-User-Id`**
- 内容类型：`application/json; charset=utf-8`
- 错误：`{"error":{"code":"...","message":"...","details":[...]}}`；不返回堆栈/内部地址
- 分页：`limit`(1–200, 默认50)、`offset`(≥0)
- 审计：所有写操作由服务端记录 actor/action/target/detail/time

## 1. 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/auth/login | `{username,password}` → `{token,expires_at,user}`；错误 401 `invalid_credentials` |
| POST | /api/auth/wx-login | `{code}` → `{token,user,mode:wechat|mock,is_new_user,note}`；未配置 WX 时 mock |
| POST | /api/auth/logout | 删除当前 Token；200 |
| GET | /api/auth/me | 当前用户与 permissions |

## 2. 模板与应用

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/templates | 登录 | 模板列表（不含提示词全文） |
| GET | /api/templates/{key} | 登录 | 模板详情（含提示词预览） |
| GET | /api/apps | 登录 | 列表；creator/dept 仅本部门 |
| POST | /api/apps | app:create | `{name,template_key,department?}` → 201 应用（draft） |
| GET | /api/apps/{id} | 可见 | 详情 + 发布检查 + 审批 + 版本 |
| PUT | /api/apps/{id} | app:edit | 仅 draft/testing；`{model_policy?,knowledge_scope?,channels?,temperature?,memory_enabled?,memory_write_mode?,memory_search_mode?}` |
| POST | /api/apps/{id}/trial | app:trial | `{query, session_id?}` → 输出/引用/免责/版本/降级/安全/执行轨迹/自动记忆；返回 run_id/session_id |
| POST | /api/apps/{id}/feedback | app:trial | `{helpful,question,output,reason,comment}` → 无用进入 BadCase |
| POST | /api/apps/{id}/sessions | app:trial | 创建调试会话 |
| POST | /api/sessions/{id}/close | app:trial/管理员 | 结束会话；session 模式写摘要记忆 |
| GET | /api/runs | metrics:read | 试跑运行记录（app_id/session_id 过滤） |
| GET | /api/apps/{id}/release-check | 可见 | `{items:[{key,label,ok,detail}],ready}` |
| POST | /api/apps/{id}/submit | app:submit | 门禁通过 → 404/409 `release_blocked`（含 details）→ 200 pending_dept |
| POST | /api/apps/{id}/disable | approval:platform | 停用 |
| POST | /api/apps/{id}/rollback | approval:platform | `{version}` → 恢复该版本配置，current_version=version |
| GET | /api/apps/{id}/versions | 可见 | 版本快照列表 |
| GET | /api/approvals | dept/platform/admin | 待审批列表（按角色过滤） |
| POST | /api/approvals/{id}/decide | approval:dept/platform | `{decision:approve\|reject,comment}`；科室通过生成平台审批；平台通过发布 |

## 3. 知识

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/knowledge | knowledge:read | 列表（可按 status/scope/q） |
| POST | /api/knowledge | knowledge:write | `{title,source,owner,scope[],effective_at,expires_at?,version?,content}` → 201 pending |
| POST | /api/knowledge/{id}/review | knowledge:review | `{decision:approve\|reject,comment?}` |
| GET | /api/knowledge/search?q= | knowledge:read | 仅 approved + 生效期内 + 范围；返回文档+FAQ 引用 |
| GET | /api/knowledge/{id} | knowledge:read | 详情 |
| GET | /api/faqs | knowledge:read | FAQ 列表（status/q） |
| POST | /api/faqs | knowledge:write | `{question,answer,source?,scope?}` → 201 pending |
| POST | /api/faqs/{id}/review | knowledge:review | `{decision:approve\|reject,comment?}`，通过后参与检索 |

## 4. 模型

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/models | model:read | 模型列表 |
| PUT | /api/models/{key} | model:write | `{status:enabled\|disabled}` |
| GET | /api/model-policies | model:read | 策略链/超时/降级模式 |
| POST | /api/model-policies/{key}/test | model:read | 网关测试；降级显式返回 |
| GET | /api/model-calls | model:read | 调用记录（降级/延迟/tokens） |

## 5. 评测

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/eval/datasets | metrics:read | 数据集+用例数+指标定义 |
| POST | /api/eval/run | eval:run | `{app_id,dataset_key?}` → metrics/gate_status/passed |
| GET | /api/eval/runs | metrics:read | 评测记录 |
| GET | /api/eval/runs/{id} | metrics:read | 详情（逐用例结果） |

## 6. 运营 / BadCase / 审计

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/ops/metrics | metrics:read | 指标定义+当前值 |
| GET | /api/ops/alerts | metrics:read | 运营告警（风险/积压/失败/降级） |
| GET | /api/dashboard | metrics:read | 指标+检查清单+最近应用/审计 |
| GET | /api/badcases | metrics:read | 列表 |
| POST | /api/badcases | badcase:manage | 登记 |
| POST | /api/badcases/{id} | badcase:manage | `{action:assign\|close, assignee?/resolution?}` |
| GET | /api/safety/events | audit:read | 安全事件 |
| GET | /api/audit | audit:read | 审计列表 |
| GET | /api/audit/export | audit:export | 导出 JSON（留痕） |
| GET | /api/handoffs | patient:manage | 随访转人工待办 |

## 7. 患者端（小程序）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/patient/me | 绑定/授权/报告数/任务数 |
| POST | /api/patient/bind | `{patient_ref,verify_code}`（POC 654321）→ 绑定+授权 |
| POST | /api/patient/revoke | `{action:revoke\|unbind}` |
| GET | /api/patient/reports | 仅授权且 `approved_for_patient=1` |
| GET | /api/patient/followups | 仅授权随访 |
| POST | /api/patient/followups/{id}/submit | `{answers:{}}`；危险信号→200 `{risk_flag:true,handoff:true,...}` |

## 8. 错误码

| code | HTTP | 含义 |
|---|---|---|
| unauthorized | 401 | 未登录/Token 过期 |
| invalid_credentials | 401 | 账号或密码错误 |
| wx_login_failed / wx_upstream | 401/502 | 微信登录失败/上游不可用 |
| forbidden | 403 | 无权限/越权 |
| not_found | 404 | 资源不存在 |
| validation | 400 | 参数校验失败 |
| release_blocked | 409 | 发布检查未通过（details 逐项） |
| conflict | 409 | 状态冲突（已审批/已停用等） |
| method_not_allowed | 405 | 方法不支持 |
| internal_error | 500 | 内部错误（不返回堆栈） |

## 9. 安全约定（v1.1 §8）

- `X-User-Id` 仅可用于隔离 mock；本服务默认拒绝，身份从服务端 Token 解析；
- 患者接口在服务端校验“用户—patient_ref—授权范围”，不依赖前端隐藏；
- 微信 openid 不等同医疗身份，绑定需核验+授权；
- 模型调用日志按最小必要记录；患者敏感信息不进入普通日志；
- 写操作幂等/重复提交由状态机与审批状态约束（重复审批 409）。

## 10. 记忆（扩展，AgentHub v1.2 重建）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /api/memories | memory:read | 列表/统计；筛选 scope/type/status/q |
| GET | /api/memories/search?q=&mode=vector\|bigram | memory:read | 64 维向量/关键词检索（返回 score） |
| POST | /api/memories | memory:write | `{scope:user\|agent\|tenant, owner?, type, content, importance?, expires_at?}`；重复内容返回 200 `deduped=true` |
| PUT | /api/memories/{id} | memory:write | 更新 content/importance/expires_at/status（非管理员仅 user 范围本人） |
| DELETE | /api/memories/{id} | memory:write | 软删；`?hard=1` 仅管理员硬删 |

试跑注入：应用配置 `memory_enabled=true` 时，按 `memory_search_mode`（vector/bigram）检索 user=当前用户、agent=当前应用、tenant=default 的活跃未过期记忆 Top3，输出标注「结合历史记忆」，Trace 增加 `memory` 步骤并累计 `use_count`。

写入模式（应用 config `memory_write_mode`）：
- `off`：不自动写；
- `session`：`POST /api/sessions/{id}/close` 时汇总会话 runs 写 `user` 范围 summary；
- `auto`：每次试跑后立即写 `agent` 范围 summary（`runs.memory_written=1`，Trace 增加“自动写入摘要”步骤）。

患者端不使用临床记忆。
