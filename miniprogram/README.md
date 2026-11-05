# MediAgent 患者服务小程序（POC）

与 `medagent-platform` 中台联动的患者端：微信登录 → 绑定患者身份 → 查看报告 → 填写随访。

## 导入与运行

1. 启动中台：
   ```powershell
   cd medagent-platform
   python server/app.py --port 8090 --db data/medagent.db --reset
   ```
2. 微信开发者工具 → 导入项目 → 目录选 `miniprogram`，AppID 用测试号；
3. 「详情 → 本地设置」勾选「不校验合法域名、web-view、TLS 版本以及 HTTPS 证书」；
4. 修改 `config.js` 的 `BASE_URL`：
   - 模拟器：`http://127.0.0.1:8090`
   - 真机：`http://<电脑局域网IP>:8090`，服务端需 `--host 0.0.0.0`，手机同网、防火墙放行；
5. 编译：首页自动 `wx.login` → `/api/auth/wx-login`（服务端未配置 WX 时走 dev mock）；
6. 点「绑定患者身份」：患者标识 `P0001` 或 `P0002`，核验码 `654321`（POC）；
7. 绑定后可查看「我的报告」「随访任务」；随访填写 `{"symptom":"胸痛"}` 可触发危险信号 → 人工待办。

## 接口依赖

| 页面 | 中台接口 |
|---|---|
| 登录 | `POST /api/auth/wx-login {code}` → Token |
| 首页 | `GET /api/patient/me` |
| 绑定 | `POST /api/patient/bind {patient_ref, verify_code}` |
| 报告 | `GET /api/patient/reports`（仅 `approved_for_patient=1`） |
| 随访 | `GET /api/patient/followups`、`POST /api/patient/followups/{id}/submit {answers}` |

## 安全边界

- 微信 openid 仅用于会话，不等于医疗身份；绑定需核验+授权；
- 患者端不提供诊断/处方/用药调整；危险信号提示就医并生成人工待办；
- 报告仅展示院方批准向患者开放的内容；默认不展示姓名/证件等直接标识。

## 生产前必须完成

- 正式小程序 AppID/主体、HTTPS 备案域名、request 合法域名；
- 真实身份核验（手机号/就诊卡/HIS）与隐私保护指引；
- 订阅消息模板（随访提醒/报告出具）、内容安全审核；
- 正式免责声明、患者授权撤回流程、审计与留存策略；
- 真机与多版本微信兼容性测试。

> API 细节见中台 [`docs/api-contract.md`](../docs/api-contract.md) 与 [`docs/requirements-mapping.md`](../docs/requirements-mapping.md)。
