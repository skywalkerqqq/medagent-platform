# 压测基线（本机 POC）

> 时间：2026-10-31 ｜ 环境：Windows 开发机，Python 3.12，`server/app.py` 单进程 stdlib 服务 + SQLite
> 命令：
> ```powershell
> python scripts/load_test.py --base-url http://127.0.0.1:8090 \
>   --username u_admin --password medagent123 --path /api/apps \
>   --requests 200 --concurrency 10 --out data/load-baseline.json
> ```
> 结果：200 请求 / 并发 10 / 0 错误

| 指标 | 数值 |
|---|---|
| QPS | 972 |
| P50 | 7.02 ms |
| P95 | 27.76 ms |
| P99 | 30.06 ms |
| 最大 | 31.82 ms |
| HTTP 状态 | 200 × 200 |

## 必须说明

- 这是 **本机、小数据量、只读列表接口** 的基线，**不是生产容量承诺**；
- 未包含真实登录/试跑/模型调用（这些会受上游模型与 SQLite 写锁影响）；
- 单 worker + SQLite 是明确瓶颈：并发写、复杂检索、报告/评测会显著下降；
- 生产压测必须在目标网络、真实数据量、真实模型上游、目标并发下重跑，并覆盖登录、试跑、知识检索、报告签名、审计校验等关键链路。

## 下一步压测项

1. `POST /api/apps/{id}/trial`（含模板/知识/安全/记忆，模拟上游）；
2. 知识检索（大文档量）；
3. 报告编辑/签名 + 审计链校验；
4. 混合读写 + 并发上传/导出审计；
5. 限流开启（`RATE_LIMIT_RPS`）下的 429 行为与恢复。
