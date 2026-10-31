/* MediAgent 医疗 AI 中台 v1.1 · 前端（原生 ES Module，无构建） */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  token: localStorage.getItem('ma_token') || '',
  user: JSON.parse(localStorage.getItem('ma_user') || 'null'),
  templates: [],
  view: null,
};

const NAV = [
  { group: '工作台', items: [
    { key: 'dashboard', label: '总览 / 验收', icon: '◈', path: '/dashboard' },
    { key: 'apps', label: '应用工厂', icon: '▤', path: '/apps' },
  ] },
  { group: '能力', items: [
    { key: 'knowledge', label: '知识中心', icon: '▥', path: '/knowledge' },
    { key: 'models', label: '模型网关', icon: '◫', path: '/models' },
    { key: 'eval', label: '评测门禁', icon: '◎', path: '/eval' },
  ] },
  { group: '治理与运营', items: [
    { key: 'ops', label: '运营 / BadCase', icon: '▦', path: '/ops' },
    { key: 'patient', label: '患者端演示', icon: '♙', path: '/patient' },
  ] },
];

const TITLES = {
  '/login': ['登录', 'MediAgent / 登录'],
  '/dashboard': ['总览 / 验收', '工作台 / 总览'],
  '/apps': ['应用工厂', '工作台 / 应用工厂'],
  '/knowledge': ['知识中心', '能力 / 知识中心'],
  '/models': ['模型网关', '能力 / 模型网关'],
  '/eval': ['评测门禁', '能力 / 评测门禁'],
  '/ops': ['运营 / BadCase', '治理 / 运营'],
  '/patient': ['患者端演示', '渠道 / 小程序患者端'],
};

function esc(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function toast(message, type = '') {
  const el = $('#toast');
  el.textContent = message;
  el.className = `toast ${type === 'error' ? 'error' : ''}`;
  el.classList.remove('hidden');
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => el.classList.add('hidden'), 3800);
}

function pct(value) {
  if (value === null || value === undefined || value === '') return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

function statusPill(status) {
  const map = {
    draft: ['草稿', 'gray'], testing: ['测试中', 'teal'],
    pending_dept: ['待科室审批', 'amber'], pending_platform: ['待平台审批', 'violet'],
    published: ['已发布', 'green'], disabled: ['已停用', 'red'],
    approved: ['已通过', 'green'], rejected: ['已拒绝', 'red'], pending: ['待审核', 'amber'],
    open: ['待处理', 'red'], assigned: ['处理中', 'amber'], closed: ['已关闭', 'gray'],
    finished: ['已完成', 'green'], passed: ['通过', 'green'], failed: ['未通过', 'red'],
    active: ['生效', 'green'], revoked: ['已撤回', 'gray'],
  };
  const [label, tone] = map[status] || [status || '—', 'gray'];
  return `<span class="pill ${tone}">${esc(label)}</span>`;
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, {
    method: options.method || 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  let data = null;
  try { data = await response.json(); } catch (error) { data = null; }
  if (response.status === 401) {
    logout(false);
    throw new Error('登录已过期，请重新登录');
  }
  if (!response.ok) {
    const detail = data && data.error ? data.error : { message: `请求失败（HTTP ${response.status}）` };
    const err = new Error(detail.message || '请求失败');
    err.code = detail.code;
    err.details = detail.details;
    throw err;
  }
  return data;
}

function logout(redirect = true) {
  state.token = '';
  state.user = null;
  localStorage.removeItem('ma_token');
  localStorage.removeItem('ma_user');
  if (redirect) route();
}

function has(permission) {
  const perms = (state.user && state.user.permissions) || [];
  return perms.includes('admin') || perms.includes(permission);
}

function canAny() { return state.user !== null; }

function layout() {
  const nav = $('#nav');
  nav.innerHTML = NAV.map((group) => `
    <div class="nav-group">${group.group}</div>
    ${group.items.map((item) => `<a class="nav-item" href="#${item.path}" data-key="${item.key}">
      <span class="nav-icon">${item.icon}</span><span class="nav-label">${esc(item.label)}</span>
    </a>`).join('')}
  `).join('');
  const user = state.user;
  $('#user-mini').innerHTML = user
    ? `<strong>${esc(user.name)}</strong><br>${esc(user.role)} · ${esc(user.department || '')}`
    : '未登录';
}

function setHeader(path) {
  const [title, crumb] = TITLES[path] || ['MediAgent', 'MediAgent'];
  $('#page-title').textContent = title;
  $('#page-crumb').textContent = crumb;
  document.title = `MediAgent · ${title}`;
}

function route() {
  const raw = window.location.hash.replace(/^#/, '') || '/dashboard';
  const path = raw.split('?')[0];
  const view = $('#view');
  state.view = view;
  layout();
  if (path === '/login') {
    if (state.token && state.user) {
      window.location.hash = '#/dashboard';
      return;
    }
    setHeader('/login');
    $('#top-actions').innerHTML = '';
    renderLogin(view);
    return;
  }
  if (!state.token || !state.user) {
    window.location.hash = '#/login';
    return;
  }
  setHeader(path);
  $('#top-actions').innerHTML = `<span class="small muted">${esc(state.user.name)} · ${esc(state.user.role)}</span>`;
  $$('#nav .nav-item').forEach((item) => {
    const active = path === item.dataset.key || (path.startsWith('/apps/') && item.dataset.key === 'apps');
    item.classList.toggle('active', active);
  });
  const matched = path.match(/^\/apps\/(\d+)$/);
  if (matched) {
    $('#page-title').textContent = '应用详情';
    $('#page-crumb').textContent = '工作台 / 应用工厂 / 详情';
    renderAppDetail(view, matched[1]);
    return;
  }
  const pages = {
    '/dashboard': renderDashboard,
    '/apps': renderApps,
    '/knowledge': renderKnowledge,
    '/models': renderModels,
    '/eval': renderEval,
    '/ops': renderOps,
    '/patient': renderPatient,
  };
  const page = pages[path];
  if (!page) {
    view.innerHTML = `<div class="card">页面不存在：${esc(path)}</div>`;
    return;
  }
  page(view);
}

/* ---------------------------------------------------------------- 登录 */
function renderLogin(view) {
  view.innerHTML = `
    <div class="login-wrap">
      <div class="login-logo">M</div>
      <h1 class="login-title">MediAgent 医疗 AI 中台</h1>
      <p class="login-sub">v1.1 · 服务端 Token 会话身份 · 应用工厂 / 知识治理 / 评测门禁 / 患者端联动</p>
      <div class="card">
        <form id="login-form">
          <label class="field"><span>用户名</span><input id="login-user" value="u_creator" autocomplete="username" /></label>
          <label class="field"><span>密码</span><input id="login-pass" type="password" value="medagent123" autocomplete="current-password" /></label>
          <button class="btn btn-primary" style="width:100%" type="submit">登录</button>
        </form>
        <div class="demo-accounts">
          演示账号（密码均为 <code>medagent123</code>）：<br>
          <code>u_creator</code> 业务人员 · <code>u_dept</code> 科室审批人 · <code>u_platform</code> 平台审批人<br>
          <code>u_knowledge</code> 知识运营 · <code>u_eval</code> 评测 · <code>u_doctor</code> 医生 · <code>u_patient</code> 患者
        </div>
      </div>
    </div>`;
  $('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: { username: $('#login-user').value.trim(), password: $('#login-pass').value },
      });
      state.token = data.token;
      state.user = data.user;
      localStorage.setItem('ma_token', data.token);
      localStorage.setItem('ma_user', JSON.stringify(data.user));
      window.location.hash = '#/dashboard';
      route();
      toast(`欢迎，${data.user.name}`);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

/* ---------------------------------------------------------------- 总览 */
function taskStatusPill(status) {
  const map = { pending: ['待随访', 'teal'], submitted: ['已提交', 'green'], handoff: ['已转人工', 'red'], closed: ['已结束', 'gray'] };
  const [label, tone] = map[status] || [status || '—', 'gray'];
  return `<span class="pill ${tone}">${esc(label)}</span>`;
}

async function renderDashboard(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [dash, metrics] = await Promise.all([api('/api/dashboard'), api('/api/ops/metrics')]);
    const m = metrics.values;
    view.innerHTML = `
      <div class="grid grid-4">
        ${kpi('应用总数', m.apps_total, `已发布 ${m.apps_published}`, 'teal')}
        ${kpi('评测通过率', pct(m.eval_pass_rate), '门禁通过 / 评测总数', 'green')}
        ${kpi('未闭环 BadCase', m.badcase_open, '需指派/关闭', 'amber')}
        ${kpi('高风险安全事件', m.safety_high, '安全阻断项', 'violet')}
        ${kpi('模型调用', m.model_calls, `降级率 ${pct(m.degrade_rate)}`, 'teal')}
        ${kpi('模型 P95 延迟', `${m.p95_latency_ms || 0}ms`, '仅模型耗时', 'green')}
        ${kpi('生效知识', m.knowledge_approved, `待审核 ${m.knowledge_pending}`, 'teal')}
        ${kpi('待审批', dash.pending_approvals, '科室/平台审批', 'amber')}
      </div>
      <div class="grid grid-2" style="margin-top:20px">
        <div class="card">
          <h3 class="section-title">v1.1 发布前检查清单</h3>
          <p class="section-sub">来自落地执行包 v1.1 第 14 节；未勾选项需项目方确认。</p>
          ${dash.release_checklist.map((item) => `<div class="check-row">
            <span class="check-mark ${item.done ? 'ok' : 'bad'}">${item.done ? '✓' : '!'}</span>
            <div class="small">${esc(item.item)}</div>
          </div>`).join('')}
        </div>
        <div class="card">
          <h3 class="section-title">应用状态分布</h3>
          <div class="list">
            ${Object.entries(dash.apps_by_status).map(([status, count]) => `<div class="list-item">
              <div class="list-main">${statusPill(status)}</div>
              <div class="list-actions"><strong>${count}</strong></div>
            </div>`).join('') || '<div class="muted small">暂无应用</div>'}
          </div>
          <h3 class="section-title" style="margin-top:20px">最近应用</h3>
          <div class="table-wrap"><table><thead><tr><th>编号</th><th>名称</th><th>状态</th><th>版本</th><th>科室</th></tr></thead><tbody>
            ${dash.recent_apps.map((app) => `<tr><td class="mono">${esc(app.code)}</td><td>${esc(app.name)}</td>
              <td>${statusPill(app.status)}</td><td>v${app.current_version || 0}</td><td>${esc(app.department || '')}</td></tr>`).join('')}
          </tbody></table></div>
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">最近审计</h3>
        <div class="table-wrap"><table><thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>对象</th><th>详情</th></tr></thead><tbody>
          ${dash.recent_audit.map((row) => `<tr><td class="small muted">${esc(row.created_at)}</td><td class="mono">${esc(row.actor)}</td>
            <td>${esc(row.action)}</td><td class="small">${esc(row.target_type)} ${esc(row.target_id)}</td>
            <td class="small muted">${esc(row.detail)}</td></tr>`).join('')}
        </tbody></table></div>
      </div>`;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

function kpi(label, value, sub, tone = 'teal') {
  return `<div class="card kpi ${tone}"><div class="kpi-label">${esc(label)}</div>
    <div class="kpi-value">${esc(value)}</div><div class="kpi-sub">${esc(sub)}</div></div>`;
}

/* ---------------------------------------------------------------- 应用工厂 */
async function renderApps(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [apps, templates] = await Promise.all([api('/api/apps'), api('/api/templates')]);
    state.templates = templates.items;
    const canCreate = has('app:create');
    view.innerHTML = `
      ${canCreate ? `<div class="card">
        <h3 class="section-title">从模板创建应用</h3>
        <p class="section-sub">模板定义提示词、知识范围、模型策略与评测门禁；创建后先试跑，再走发布检查与双审批。</p>
        <div class="form-row">
          <label class="field"><span>应用名称</span><input id="app-name" placeholder="例如：心内科知识助手" /></label>
          <label class="field"><span>模板</span><select id="app-template">
            ${state.templates.map((t) => `<option value="${esc(t.key)}">${esc(t.name)}（v${t.version} · ${esc(t.risk_level)} · 阈值 ${t.eval_threshold}）</option>`).join('')}
          </select></label>
        </div>
        <div class="form-actions"><button class="btn btn-primary" onclick="MA.createApp()">创建草稿</button></div>
      </div>` : ''}
      <div class="card">
        <h3 class="section-title">应用列表 <span class="muted small">（${apps.total}）</span></h3>
        <div class="table-wrap"><table><thead><tr><th>编号</th><th>名称</th><th>模板</th><th>状态</th><th>版本</th><th>最近评测</th><th>操作</th></tr></thead><tbody>
          ${apps.items.map((app) => `<tr>
            <td class="mono">${esc(app.code)}</td>
            <td><strong>${esc(app.name)}</strong><div class="small muted">${esc(app.department)}</div></td>
            <td class="small">${esc(app.template_name)}</td>
            <td>${statusPill(app.status)}</td>
            <td>v${app.current_version || 0}</td>
            <td>${app.latest_eval ? `${statusPill(app.latest_eval.gate_status)}<span class="small muted"> run#${app.latest_eval.id}</span>` : '<span class="muted small">未评测</span>'}</td>
            <td><a class="btn btn-outline btn-sm" href="#/apps/${app.id}">打开</a></td>
          </tr>`).join('') || '<tr><td colspan="7" class="muted">暂无应用</td></tr>'}
        </tbody></table></div>
      </div>`;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function createApp() {
  const name = $('#app-name').value.trim();
  const templateKey = $('#app-template').value;
  if (!name) { toast('请输入应用名称', 'error'); return; }
  try {
    const app = await api('/api/apps', { method: 'POST', body: { name, template_key: templateKey } });
    toast(`已创建 ${app.code}`);
    window.location.hash = `#/apps/${app.id}`;
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------------------------------------------------------------- 应用详情 */
async function renderAppDetail(view, id) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [app, approvals] = await Promise.all([api(`/api/apps/${id}`), api('/api/approvals?status=pending').catch(() => ({ items: [] }))]);
    const pendingForApp = approvals.items.filter((item) => item.app_id === Number(id));
    const canEdit = has('app:edit') && (state.user.id === app.owner_id || has('admin'));
    const canSubmit = has('app:submit') && (state.user.id === app.owner_id || has('admin')) && ['draft', 'testing'].includes(app.status);
    const canPlatform = has('approval:platform');
    const release = app.release_check;
    view.innerHTML = `
      <div class="card">
        <div class="btn-row" style="justify-content:space-between">
          <div>
            <div class="btn-row"><strong style="font-size:20px">${esc(app.name)}</strong> ${statusPill(app.status)}
              <span class="small muted mono">${esc(app.code)}</span></div>
            <div class="small muted" style="margin-top:6px">${esc(app.department)} · ${esc(app.template_name)} v${app.template_version} · 当前版本 v${app.current_version || 0} · 创建人 ${esc(app.owner_id)}</div>
          </div>
          <div class="btn-row">
            ${canSubmit ? '<button class="btn btn-primary" onclick="MA.submitApp()">提交发布检查</button>' : ''}
            ${canPlatform && app.status === 'published' ? '<button class="btn btn-danger btn-sm" onclick="MA.disableApp()">停用</button>' : ''}
          </div>
        </div>
      </div>
      <div class="grid grid-2" style="margin-top:20px">
        <div class="card">
          <h3 class="section-title">发布检查（门禁）</h3>
          <div class="list">
            ${release.items.map((item) => `<div class="check-row">
              <span class="check-mark ${item.ok ? 'ok' : 'bad'}">${item.ok ? '✓' : '!'}</span>
              <div><div class="small"><strong>${esc(item.label)}</strong></div><div class="small muted">${esc(item.detail)}</div></div>
            </div>`).join('')}
          </div>
          <div class="alert ${release.ready ? 'green' : 'amber'}">${release.ready ? '自动检查通过：可提交，进入科室审批与平台审批。' : '未通过项将阻断发布（不能以平均分豁免高风险/越权问题）。'}</div>
        </div>
        <div class="card">
          <h3 class="section-title">配置与版本快照</h3>
          <div class="small"><b>模型策略：</b>${esc(app.config.model_policy)}</div>
          <div class="small"><b>知识范围：</b>${(app.config.knowledge_scope || []).join('、')}</div>
          <div class="small"><b>渠道：</b>${(app.config.channels || []).join('、')}</div>
          <div class="small"><b>风险等级：</b>${esc(app.risk_level)}</div>
          <div class="small"><b>模板/提示词版本：</b>v${app.template_version}</div>
          <div class="small muted" style="margin-top:10px">发布版本会固定模板/提示词/模型/知识/评测集/审批记录（FR-005、6.4）。</div>
          <h3 class="section-title" style="margin-top:18px">版本历史</h3>
          ${app.versions.length ? `<div class="table-wrap"><table><thead><tr><th>版本</th><th>状态</th><th>发布人</th><th>时间</th><th></th></tr></thead><tbody>
            ${app.versions.map((v) => `<tr><td>v${v.version}</td><td>${statusPill(v.status === 'published' ? 'published' : 'draft')}</td>
              <td class="mono small">${esc(v.created_by || '')}</td><td class="small muted">${esc(v.published_at || v.created_at)}</td>
              <td>${canPlatform && v.version !== app.current_version ? `<button class="btn btn-outline btn-sm" onclick="MA.rollback(${v.version})">回滚</button>` : ''}</td></tr>`).join('')}
          </tbody></table></div>` : '<div class="muted small">暂无版本</div>'}
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">试跑（不发布也能验证）</h3>
        <p class="section-sub">试跑显示输出、引用、免责声明、版本与降级标记；模型不可用时按故障安全提示人工处理。</p>
        <label class="field"><span>输入（知识问答：问题；病历质控：病历文本）</span>
          <textarea id="trial-input" placeholder="例如：社区获得性肺炎抗感染治疗原则是什么？"></textarea></label>
        <div class="form-actions"><button class="btn btn-primary" onclick="MA.trial(${app.id})">试跑</button></div>
        <div id="trial-result" style="margin-top:16px"></div>
      </div>
      <div class="card">
        <h3 class="section-title">审批记录</h3>
        ${app.approvals.length ? `<div class="table-wrap"><table><thead><tr><th>类型</th><th>状态</th><th>审批人</th><th>意见</th><th>时间</th><th>操作</th></tr></thead><tbody>
          ${app.approvals.map((item) => `<tr><td>${item.kind === 'dept' ? '科室审批' : '平台审批'}</td><td>${statusPill(item.status)}</td>
            <td class="mono small">${esc(item.reviewer_id || '—')}</td><td class="small">${esc(item.comment || '')}</td>
            <td class="small muted">${esc(item.decided_at || item.created_at)}</td>
            <td>${item.status === 'pending' ? approveButtons(item) : '—'}</td></tr>`).join('')}
        </tbody></table></div>` : '<div class="muted small">暂无审批记录（提交发布后生成科室→平台两级审批）</div>'}
        ${pendingForApp.length ? '' : ''}
      </div>`;
    window.MA = window.MA || {};
    window.MA.currentAppId = Number(id);
    window.MA.currentApp = app;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

function approveButtons(item) {
  const kind = item.kind;
  const allowed = (kind === 'dept' && (has('approval:dept') || has('admin'))) ||
    (kind === 'platform' && (has('approval:platform') || has('admin')));
  if (!allowed) return '<span class="muted small">无权限</span>';
  return `<div class="btn-row"><button class="btn btn-ok btn-sm" onclick="MA.decide(${item.id},'approve')">通过</button>
    <button class="btn btn-danger btn-sm" onclick="MA.decide(${item.id},'reject')">拒绝</button></div>`;
}

async function trial(appId) {
  const input = $('#trial-input').value.trim();
  if (!input) { toast('请输入内容', 'error'); return; }
  const box = $('#trial-result');
  box.innerHTML = '<div class="muted small">试跑中…</div>';
  try {
    const result = await api(`/api/apps/${appId}/trial`, { method: 'POST', body: { query: input } });
    const safety = result.safety || {};
    box.innerHTML = `
      ${result.degraded ? `<div class="alert amber">降级/阻断标记：当前输出非主模型或已触发安全处置，不得当作真实模型结果。</div>` : ''}
      ${safety.blocked ? `<div class="alert red">安全阻断：命中 ${esc((safety.categories || []).join(','))}，已转人工。</div>` : ''}
      <div class="pre">${esc(result.output)}</div>
      ${result.citations && result.citations.length ? `<div class="citations">${result.citations.map((c) => `<span class="citation">${esc(c.citation || c.title)}</span>`).join('')}</div>` : '<div class="alert amber">无可用引用：按规则必须拒答或提示人工，不得编造。</div>'}
      <div class="small muted" style="margin-top:10px">版本：${esc(JSON.stringify(result.versions))} · 延迟 ${result.latency_ms}ms · tokens ${result.tokens}</div>`;
  } catch (error) {
    box.innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
  }
}

async function submitApp() {
  const id = window.MA.currentAppId;
  try {
    await api(`/api/apps/${id}/submit`, { method: 'POST' });
    toast('已提交：进入科室审批');
    route();
  } catch (error) {
    const items = (error.details || []).map((item) => `<li>${esc(item.label)}：${esc(item.detail)}</li>`).join('');
    toast(error.message + (items ? '（' + error.details.map((i) => i.label).join('、') + '）' : ''), 'error');
  }
}

async function decide(approvalId, decision) {
  const comment = decision === 'reject' ? (window.prompt('请输入拒绝原因（必填）') || '') : (window.prompt('审批意见（可选）') || '');
  if (decision === 'reject' && !comment) { toast('拒绝必须填写原因', 'error'); return; }
  try {
    const result = await api(`/api/approvals/${approvalId}/decide`, { method: 'POST', body: { decision, comment } });
    toast(decision === 'approve' ? '审批通过' : '已拒绝');
    route();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function rollback(version) {
  if (!window.confirm(`确认回滚到 v${version}？当前版本将切换。`)) return;
  try {
    await api(`/api/apps/${window.MA.currentAppId}/rollback`, { method: 'POST', body: { version } });
    toast(`已回滚到 v${version}`);
    route();
  } catch (error) { toast(error.message, 'error'); }
}

async function disableApp() {
  if (!window.confirm('确认停用该应用？')) return;
  try {
    await api(`/api/apps/${window.MA.currentAppId}/disable`, { method: 'POST' });
    toast('已停用');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 知识中心 */
async function renderKnowledge(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const data = await api('/api/knowledge?limit=100');
    const canWrite = has('knowledge:write');
    const canReview = has('knowledge:review');
    view.innerHTML = `
      <div class="grid grid-2">
        ${canWrite ? `<div class="card">
          <h3 class="section-title">导入知识（进入待审核）</h3>
          <form id="knowledge-form">
            <label class="field"><span>标题</span><input id="k-title" required /></label>
            <div class="form-row">
              <label class="field"><span>来源</span><input id="k-source" placeholder="指南/院内制度/说明书" required /></label>
              <label class="field"><span>责任人</span><input id="k-owner" value="知识运营" required /></label>
            </div>
            <div class="form-row">
              <label class="field"><span>生效日期（ISO）</span><input id="k-effective" value="2026-10-01T00:00:00+08:00" required /></label>
              <label class="field"><span>失效日期（可选）</span><input id="k-expires" placeholder="2027-10-01T00:00:00+08:00" /></label>
            </div>
            <label class="field"><span>适用范围（逗号分隔）</span><input id="k-scope" value="公共,心血管内科" /></label>
            <label class="field"><span>内容</span><textarea id="k-content" required></textarea></label>
            <button class="btn btn-primary" type="submit">导入并提交审核</button>
          </form>
        </div>` : ''}
        <div class="card">
          <h3 class="section-title">检索测试</h3>
          <p class="section-sub">仅返回“已审核 + 生效期内 + 范围内”的知识；过期/待审核/无权限不可见。</p>
          <div class="btn-row"><input id="k-query" placeholder="输入关键词，如：输血知情同意" />
            <button class="btn btn-outline" onclick="MA.searchKnowledge()">检索</button></div>
          <div id="k-search-result" style="margin-top:12px"></div>
          <h3 class="section-title" style="margin-top:20px">状态说明</h3>
          <div class="small muted" style="line-height:1.8">
            待审核知识不进入检索；过期知识不进入检索；审核拒绝不进入检索；删除/下架/权限调整均留痕（v1.1 §4.2）。
          </div>
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">知识清单 <span class="muted small">（${data.total}）</span></h3>
        <div class="table-wrap"><table><thead><tr><th>标题</th><th>来源</th><th>范围</th><th>版本</th><th>生效/失效</th><th>状态</th><th>操作</th></tr></thead><tbody>
          ${data.items.map((doc) => `<tr>
            <td><strong>${esc(doc.title)}</strong><div class="small muted">${esc(doc.code)}</div></td>
            <td class="small">${esc(doc.source)}</td><td class="small">${(doc.scope || []).join('、')}</td>
            <td>v${doc.version}</td>
            <td class="small muted">${esc(doc.effective_at || '')}<br>${esc(doc.expires_at || '长期')}</td>
            <td>${statusPill(doc.status)}</td>
            <td>${doc.status === 'pending' && canReview ? `<button class="btn btn-ok btn-sm" onclick="MA.reviewDoc(${doc.id},'approve')">通过</button>
              <button class="btn btn-danger btn-sm" onclick="MA.reviewDoc(${doc.id},'reject')">拒绝</button>` : '<span class="muted small">—</span>'}</td>
          </tr>`).join('')}
        </tbody></table></div>
      </div>`;
    if (canWrite) {
      $('#knowledge-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
          await api('/api/knowledge', { method: 'POST', body: {
            title: $('#k-title').value.trim(), source: $('#k-source').value.trim(),
            owner: $('#k-owner').value.trim(), effective_at: $('#k-effective').value.trim(),
            expires_at: $('#k-expires').value.trim(),
            scope: $('#k-scope').value.split(',').map((s) => s.trim()).filter(Boolean),
            content: $('#k-content').value.trim(),
          } });
          toast('已导入，待审核');
          route();
        } catch (error) { toast(error.message, 'error'); }
      });
    }
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function searchKnowledge() {
  const query = $('#k-query').value.trim();
  if (!query) return;
  try {
    const data = await api(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
    $('#k-search-result').innerHTML = data.hits.length
      ? data.hits.map((hit) => `<div class="list-item"><div class="list-main">
          <div class="list-title">${esc(hit.title)} <span class="citation">${esc(hit.citation)}</span></div>
          <div class="list-sub">${esc(hit.excerpt)}</div></div></div>`).join('')
      : '<div class="alert amber">未命中可用知识（过期/待审核/无权限均不会返回）。</div>';
  } catch (error) { toast(error.message, 'error'); }
}

async function reviewDoc(id, decision) {
  const comment = decision === 'approve' ? '内容审核通过' : (window.prompt('拒绝原因（必填）') || '');
  if (decision === 'reject' && !comment) return;
  try {
    await api(`/api/knowledge/${id}/review`, { method: 'POST', body: { decision, comment } });
    toast(decision === 'approve' ? '已审核通过' : '已拒绝');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 模型网关 */
async function renderModels(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [models, policies] = await Promise.all([api('/api/models'), api('/api/model-policies')]);
    view.innerHTML = `
      <div class="grid grid-2">
        <div class="card">
          <h3 class="section-title">模型注册</h3>
          <div class="table-wrap"><table><thead><tr><th>模型</th><th>私有</th><th>状态</th><th>超时</th><th>说明</th></tr></thead><tbody>
            ${models.items.map((m) => `<tr><td><strong>${esc(m.name)}</strong><div class="small muted mono">${esc(m.key)}</div></td>
              <td>${m.is_private ? '<span class="pill green">私有</span>' : '<span class="pill amber">云端</span>'}</td>
              <td>${statusPill(m.status === 'enabled' ? 'active' : 'disabled')}</td>
              <td>${m.timeout_ms}ms</td><td class="small muted">${esc(m.description)}</td></tr>`).join('')}
          </tbody></table></div>
        </div>
        <div class="card">
          <h3 class="section-title">策略与降级</h3>
          <p class="section-sub">主模型不可用时按链降级，界面与日志必须明确标记降级；不得把 mock 当真实模型结果（v1.1 §8.3）。</p>
          ${policies.items.map((p) => `<div class="list-item"><div class="list-main">
            <div class="list-title">${esc(p.name)} <span class="small muted mono">${esc(p.key)}</span></div>
            <div class="list-sub">链：${esc(p.chain.join(' → '))} · 超时 ${p.timeout_ms}ms · 重试 ${p.retry}</div></div>
            <div class="list-actions"><button class="btn btn-outline btn-sm" onclick="MA.testPolicy('${esc(p.key)}')">测试</button></div>
          </div>`).join('')}
          <div id="model-test-result" style="margin-top:12px"></div>
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">最近模型调用</h3>
        <div id="model-calls" class="muted small">加载中…</div>
      </div>`;
    const calls = await api('/api/model-calls?limit=20');
    $('#model-calls').innerHTML = `<div class="table-wrap"><table><thead><tr><th>时间</th><th>应用</th><th>策略</th><th>模型</th><th>降级</th><th>延迟</th><th>tokens</th></tr></thead><tbody>
      ${calls.items.map((c) => `<tr><td class="small muted">${esc(c.created_at)}</td><td>${c.app_id || '—'}</td><td>${esc(c.policy)}</td>
        <td class="mono small">${esc(c.model_key || '—')}</td><td>${c.degraded ? '<span class="pill amber">降级</span>' : '<span class="pill green">正常</span>'}</td>
        <td>${c.latency_ms}ms</td><td>${c.tokens}</td></tr>`).join('')}
    </tbody></table></div>`;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function testPolicy(key) {
  try {
    const data = await api(`/api/model-policies/${key}/test`, { method: 'POST' });
    const r = data.result;
    $('#model-test-result').innerHTML = data.ok
      ? `<div class="alert ${r.degraded ? 'amber' : 'green'}">模型：${esc(r.model_name)}（${esc(r.model_key)}）· ${r.degraded ? '已降级，必须在界面标记' : '主模型正常'} · ${r.latency_ms}ms</div>`
      : `<div class="alert red">模型不可用：${esc(r.error_code)}。按故障安全要求应转人工，不得伪造模型结果。</div>`;
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 评测 */
async function renderEval(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [datasets, apps, runs] = await Promise.all([
      api('/api/eval/datasets'), api('/api/apps'), api('/api/eval/runs'),
    ]);
    view.innerHTML = `
      <div class="card">
        <h3 class="section-title">执行离线评测（发布门禁用）</h3>
        <p class="section-sub">指标口径：Top-k 召回 / 引用准确率 / 答案正确率 / 无依据编造率 / 缺陷检出率 / 误报率（v1.1 §7.1）。</p>
        <div class="btn-row">
          <select id="eval-app" style="max-width:320px">${apps.items.map((a) => `<option value="${a.id}">${esc(a.name)}（${esc(a.template_name)}）</option>`).join('')}</select>
          ${has('eval:run') ? '<button class="btn btn-primary" onclick="MA.runEval()">运行评测</button>' : '<span class="muted small">当前角色无评测权限（用 u_eval 登录）</span>'}
          <span class="small muted">评测集：${datasets.items.map((d) => `${esc(d.key)}（${d.case_count} 例）`).join('；')}</span>
        </div>
        <div id="eval-result" style="margin-top:14px"></div>
      </div>
      <div class="card">
        <h3 class="section-title">评测记录</h3>
        <div class="table-wrap"><table><thead><tr><th>ID</th><th>应用</th><th>阈值</th><th>门禁</th><th>指标</th><th>时间</th><th></th></tr></thead><tbody>
          ${runs.items.map((r) => `<tr><td>#${r.id}</td><td>${esc(r.app_name || r.app_id)}</td><td>${r.threshold}</td>
            <td>${statusPill(r.gate_status)}</td><td class="small mono">${esc(JSON.stringify(r.metrics))}</td>
            <td class="small muted">${esc(r.created_at)}</td>
            <td><button class="btn btn-outline btn-sm" onclick="MA.showEvalRun(${r.id})">详情</button></td></tr>`).join('')}
        </tbody></table></div>
        <div id="eval-detail" style="margin-top:12px"></div>
      </div>`;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function runEval() {
  const appId = Number($('#eval-app').value);
  $('#eval-result').innerHTML = '<div class="muted small">评测中…</div>';
  try {
    const result = await api('/api/eval/run', { method: 'POST', body: { app_id: appId } });
    $('#eval-result').innerHTML = `
      <div class="alert ${result.passed ? 'green' : 'red'}">门禁 ${result.gate_status.toUpperCase()} · 阈值 ${result.threshold} · 指标：${esc(JSON.stringify(result.metrics))}</div>
      <div class="small muted">未达标时提交发布将被阻断；高风险漏检、越权、未授权发布、审计缺失为阻断项，不能以平均分豁免。</div>`;
    toast(result.passed ? '评测通过' : '评测未达标', result.passed ? '' : 'error');
  } catch (error) {
    $('#eval-result').innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
  }
}

async function showEvalRun(id) {
  try {
    const run = await api(`/api/eval/runs/${id}`);
    $('#eval-detail').innerHTML = `
      <div class="small"><b>评测集：</b>${esc(run.dataset_id)} · <b>阈值：</b>${run.threshold} · <b>门禁：</b>${statusPill(run.gate_status)}</div>
      <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>输入</th><th>期望</th><th>输出</th><th>指标</th><th>通过</th></tr></thead><tbody>
        ${run.results.map((r) => `<tr><td class="small">${esc(r.input)}</td><td class="small">${esc(r.expected)}</td>
          <td class="small pre" style="max-width:420px">${esc(r.output).slice(0, 400)}</td>
          <td class="small mono">${esc(JSON.stringify(r.metrics))}</td>
          <td>${r.passed ? '<span class="pill green">通过</span>' : '<span class="pill red">未通过</span>'}</td></tr>`).join('')}
      </tbody></table></div>`;
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 运营 */
async function renderOps(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [metrics, badcases, events, handoffs] = await Promise.all([
      api('/api/ops/metrics'), api('/api/badcases'), api('/api/safety/events').catch(() => ({ items: [] })),
      api('/api/handoffs').catch(() => ({ items: [] })),
    ]);
    const m = metrics.values;
    const canManage = has('badcase:manage');
    view.innerHTML = `
      <div class="grid grid-4">
        ${kpi('模型调用', m.model_calls, `降级率 ${pct(m.degrade_rate)}`, 'teal')}
        ${kpi('模型 P95', `${m.p95_latency_ms}ms`, '模型耗时', 'green')}
        ${kpi('未闭环 BadCase', m.badcase_open, '需分派/关闭', 'amber')}
        ${kpi('高风险事件', m.safety_high, '阻断项', 'red')}
      </div>
      <div class="card">
        <h3 class="section-title">指标定义</h3>
        <div class="table-wrap"><table><thead><tr><th>指标</th><th>定义</th><th>数据来源</th><th>当前值</th></tr></thead><tbody>
          ${metrics.definitions.map((d) => `<tr><td>${esc(d.name)}</td><td class="small">${esc(d.definition)}</td><td class="small mono">${esc(d.source)}</td>
            <td><strong>${esc(m[d.key] === null ? '—' : m[d.key])}</strong></td></tr>`).join('')}
        </tbody></table></div>
      </div>
      <div class="card">
        <h3 class="section-title">BadCase 队列</h3>
        ${canManage ? `<p class="section-sub">支持分派与关闭；关闭需填写整改结论（FR-010）。</p>` : ''}
        <div class="table-wrap"><table><thead><tr><th>ID</th><th>应用</th><th>问题</th><th>类别</th><th>严重度</th><th>状态</th><th>处理人</th><th>操作</th></tr></thead><tbody>
          ${badcases.items.map((b) => `<tr><td>#${b.id}</td><td>${esc(b.app_name || b.app_id)}</td><td class="small">${esc(b.question)}</td>
            <td>${esc(b.category)}</td><td><span class="pill ${b.severity === 'high' ? 'red' : 'amber'}">${esc(b.severity)}</span></td>
            <td>${statusPill(b.status)}</td><td class="small mono">${esc(b.assignee || '—')}</td>
            <td>${canManage && b.status !== 'closed' ? `<button class="btn btn-outline btn-sm" onclick="MA.assignBadcase(${b.id})">分派</button>
              <button class="btn btn-ok btn-sm" onclick="MA.closeBadcase(${b.id})">关闭</button>` : '—'}</td></tr>`).join('')}
        </tbody></table></div>
      </div>
      <div class="grid grid-2">
        <div class="card">
          <h3 class="section-title">安全事件</h3>
          ${events.items.length ? events.items.map((e) => `<div class="list-item"><div class="list-main">
            <div class="list-title">${esc(e.category)} <span class="pill ${e.severity === 'high' ? 'red' : 'amber'}">${esc(e.severity)}</span></div>
            <div class="list-sub">${esc(e.detail)} · ${esc(e.created_at)}</div></div></div>`).join('') : '<div class="muted small">暂无</div>'}
        </div>
        <div class="card">
          <h3 class="section-title">随访转人工待办</h3>
          ${handoffs.items.length ? handoffs.items.map((h) => `<div class="list-item"><div class="list-main">
            <div class="list-title">任务 #${h.task_id || '—'} · ${esc(h.patient_ref)}</div>
            <div class="list-sub">${esc(h.reason)} · ${esc(h.created_at)}</div></div><div class="list-actions">${statusPill(h.status)}</div></div>`).join('') : '<div class="muted small">暂无（可在患者端演示中提交危险信号触发）</div>'}
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">审计日志</h3>
        <div class="btn-row" style="margin-bottom:10px">
          <button class="btn btn-outline btn-sm" onclick="MA.loadAudit()">加载审计</button>
          ${has('audit:export') ? '<button class="btn btn-outline btn-sm" onclick="MA.exportAudit()">导出审计（留痕）</button>' : ''}
        </div>
        <div id="audit-result" class="muted small">点击“加载审计”查看（需审计权限；导出仅管理员/平台审批人）。</div>
      </div>`;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function assignBadcase(id) {
  const assignee = window.prompt('指派给（用户 ID，如 u_knowledge）');
  if (!assignee) return;
  try {
    await api(`/api/badcases/${id}`, { method: 'POST', body: { action: 'assign', assignee } });
    toast('已分派'); route();
  } catch (error) { toast(error.message, 'error'); }
}

async function closeBadcase(id) {
  const resolution = window.prompt('整改结论（必填）');
  if (!resolution) return;
  try {
    await api(`/api/badcases/${id}`, { method: 'POST', body: { action: 'close', resolution } });
    toast('已关闭'); route();
  } catch (error) { toast(error.message, 'error'); }
}

async function loadAudit() {
  try {
    const data = await api('/api/audit?limit=100');
    $('#audit-result').innerHTML = `<div class="table-wrap"><table><thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>对象</th><th>详情</th></tr></thead><tbody>
      ${data.items.map((row) => `<tr><td class="small muted">${esc(row.created_at)}</td><td class="mono small">${esc(row.actor)}</td>
        <td>${esc(row.action)}</td><td class="small">${esc(row.target_type)} ${esc(row.target_id)}</td><td class="small muted">${esc(row.detail)}</td></tr>`).join('')}
    </tbody></table></div>`;
  } catch (error) { $('#audit-result').innerHTML = `<div class="alert red">${esc(error.message)}</div>`; }
}

async function exportAudit() {
  try {
    const data = await api('/api/audit/export');
    toast(`已导出 ${data.exported} 条（导出动作已留痕）`);
    $('#audit-result').innerHTML = `<div class="alert green">已导出 ${data.exported} 条审计记录；导出动作已写入审计。</div>`;
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 患者端 */
async function renderPatient(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const me = await api('/api/patient/me');
    if (!me.bound) {
      view.innerHTML = `
        <div class="card" style="max-width:640px">
          <h3 class="section-title">患者端登录与绑定（小程序联动演示）</h3>
          <p class="section-sub">微信 openid 不等同医疗身份；须完成院方认可的身份核验与授权后，才能访问患者专属数据（v1.1 §4.3/FR-012）。</p>
          <label class="field"><span>患者标识（演示：P0001 / P0002）</span><input id="bind-ref" value="P0001" /></label>
          <label class="field"><span>身份核验码（POC 演示：654321）</span><input id="bind-code" value="654321" /></label>
          <button class="btn btn-primary" onclick="MA.bindPatient()">绑定并授权（报告+随访）</button>
        </div>`;
      return;
    }
    const [reports, followups] = await Promise.all([
      api('/api/patient/reports').catch((e) => ({ error: e.message, items: [] })),
      api('/api/patient/followups').catch((e) => ({ error: e.message, items: [] })),
    ]);
    view.innerHTML = `
      <div class="card">
        <div class="btn-row" style="justify-content:space-between">
          <div><strong style="font-size:18px">患者 ${esc(me.name_mask)}</strong> <span class="small muted mono">${esc(me.patient_ref)}</span>
            <div class="small muted" style="margin-top:5px">授权：${esc((me.consent || []).join('、'))} · 绑定时间 ${esc(me.bound_at || '')}</div></div>
          <div class="btn-row">
            <button class="btn btn-outline btn-sm" onclick="MA.revokePatient('revoke')">撤回授权</button>
            <button class="btn btn-danger btn-sm" onclick="MA.revokePatient('unbind')">解绑</button>
          </div>
        </div>
      </div>
      <div class="grid grid-2" style="margin-top:20px">
        <div class="card">
          <h3 class="section-title">我的报告（仅已批准患者可见）</h3>
          ${reports.error ? `<div class="alert amber">${esc(reports.error)}</div>` : reports.items.length ? reports.items.map((r) => `<div class="list-item"><div class="list-main">
            <div class="list-title">${esc(r.exam_type)} <span class="pill green">已批准</span></div>
            <div class="list-sub">${esc(r.summary)} · ${esc(r.reported_at)}</div></div></div>`).join('') : '<div class="muted small">暂无</div>'}
        </div>
        <div class="card">
          <h3 class="section-title">随访任务</h3>
          ${followups.error ? `<div class="alert amber">${esc(followups.error)}</div>` : followups.items.map((task) => `<div class="list-item"><div class="list-main">
            <div class="list-title">${esc(task.node)} ${taskStatusPill(task.status)} ${task.risk_flag ? '<span class="pill red">危险信号</span>' : ''}</div>
            <div class="list-sub">截止 ${esc(task.due_at)}</div></div></div>`).join('')}
          <div style="margin-top:14px">
            <label class="field"><span>提交随访问卷（演示：填写“无症状”或“胸痛”）</span>
              <textarea id="followup-answer" placeholder='{"symptom":"无症状"}'></textarea></label>
            <button class="btn btn-primary" onclick="MA.submitFollowup()">提交随访</button>
            <div id="followup-result" style="margin-top:12px"></div>
          </div>
        </div>
      </div>`;
    window.MA.followupTaskId = followups.items && followups.items.length ? followups.items[0].id : null;
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function bindPatient() {
  try {
    const data = await api('/api/patient/bind', { method: 'POST', body: {
      patient_ref: $('#bind-ref').value.trim(), verify_code: $('#bind-code').value.trim(),
    } });
    toast('绑定成功');
    window.MA.patientBound = true;
    route();
  } catch (error) { toast(error.message, 'error'); }
}

async function revokePatient(action) {
  if (!window.confirm(action === 'unbind' ? '确认解绑？' : '确认撤回授权？')) return;
  try {
    await api('/api/patient/revoke', { method: 'POST', body: { action } });
    toast(action === 'unbind' ? '已解绑' : '已撤回授权');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

async function submitFollowup() {
  const taskId = window.MA.followupTaskId;
  if (!taskId) { toast('暂无随访任务', 'error'); return; }
  let answers = {};
  try {
    answers = JSON.parse($('#followup-answer').value || '{}');
  } catch (error) {
    answers = { symptom: $('#followup-answer').value.trim() };
  }
  try {
    const result = await api(`/api/patient/followups/${taskId}/submit`, { method: 'POST', body: { answers } });
    $('#followup-result').innerHTML = `<div class="alert ${result.risk_flag ? 'red' : 'green'}">${esc(result.message)}</div>
      <div class="small muted">${esc(result.disclaimer || '')}${result.handoff_id ? ` · 转人工待办 #${result.handoff_id}` : ''}</div>`;
    if (result.risk_flag) toast('已触发人工处置', 'error');
  } catch (error) { $('#followup-result').innerHTML = `<div class="alert red">${esc(error.message)}</div>`; }
}

/* ---------------------------------------------------------------- boot */
window.MA = {
  createApp, submitApp, decide, rollback, disableApp, trial,
  searchKnowledge, reviewDoc, testPolicy, runEval, showEvalRun,
  assignBadcase, closeBadcase, loadAudit, exportAudit,
  bindPatient, revokePatient, submitFollowup,
};

$('#logout').addEventListener('click', () => logout());
window.addEventListener('hashchange', route);
route();
