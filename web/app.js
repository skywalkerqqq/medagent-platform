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
    { key: 'dashboard', label: '总览 / 验收', icon: 'dashboard', path: '/dashboard' },
    { key: 'apps', label: '应用工厂', icon: 'layers', path: '/apps' },
    { key: 'playground', label: '运行调试', icon: 'chat', path: '/playground' },
    { key: 'reports', label: '报告编辑', icon: 'file', path: '/reports' },
  ] },
  { group: '能力', items: [
    { key: 'knowledge', label: '知识中心', icon: 'book', path: '/knowledge' },
    { key: 'memory', label: '记忆', icon: 'brain', path: '/memory' },
    { key: 'models', label: '模型网关', icon: 'cpu', path: '/models' },
    { key: 'eval', label: '评测门禁', icon: 'target', path: '/eval' },
  ] },
  { group: '集成', items: [
    { key: 'integrations', label: '数据集成（HIS/EMR/PACS）', icon: 'database', path: '/integrations' },
  ] },
  { group: '治理与运营', items: [
    { key: 'ops', label: '运营 / BadCase', icon: 'chart', path: '/ops' },
    { key: 'patient', label: '患者端演示', icon: 'user', path: '/patient' },
  ] },
];

const ICON_PATHS = {
  dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5z"/><path d="m3 13 9 5 9-5"/>',
  chat: '<path d="M21 12a8.5 8.5 0 0 1-8.5 8.5H5L3 22v-9.5A8.5 8.5 0 0 1 11.5 4h1A8.5 8.5 0 0 1 21 12z"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5v-13A2.5 2.5 0 0 1 6.5 3z"/>',
  cpu: '<rect x="7" y="7" width="10" height="10" rx="2"/><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M9 1v2M15 1v2M9 21v2M15 21v2M1 9h2M1 15h2M21 9h2M21 15h2"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  shield: '<path d="M12 3 5 6v5c0 5 3.4 8 7 10 3.6-2 7-5 7-10V6l-7-3z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  refresh: '<path d="M20 11A8 8 0 1 0 18.4 16"/><path d="M20 4v7h-7"/>',
  brain: '<path d="M9.5 3a3 3 0 0 0-3 3v1.2A3 3 0 0 0 4 10v1a3 3 0 0 0 1.5 2.6V15a3 3 0 0 0 4.5 2.6V3z"/><path d="M14.5 3a3 3 0 0 1 3 3v1.2A3 3 0 0 1 20 10v1a3 3 0 0 1-1.5 2.6V15a3 3 0 0 1-4.5 2.6V3z"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
};

function icon(name, size = 18) {
  const path = ICON_PATHS[name] || '<circle cx="12" cy="12" r="3"/>';
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}

const TITLES = {
  '/login': ['登录', 'MediAgent / 登录'],
  '/dashboard': ['总览 / 验收', '工作台 / 总览'],
  '/apps': ['应用工厂', '工作台 / 应用工厂'],
  '/playground': ['运行调试', '工作台 / 运行调试'],
  '/reports': ['报告编辑', '工作台 / 报告编辑'],
  '/knowledge': ['知识中心', '能力 / 知识中心'],
  '/memory': ['记忆', '能力 / 长期记忆'],
  '/integrations': ['数据集成', '集成 / HIS · EMR · PACS'],
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
      <span class="nav-icon">${icon(item.icon, 18)}</span><span class="nav-label">${esc(item.label)}</span>
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
    '/playground': renderPlayground,
    '/reports': renderReports,
    '/knowledge': renderKnowledge,
    '/memory': renderMemory,
    '/integrations': renderIntegrations,
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
    <div class="auth-page">
      <section class="auth-brand">
        <div class="auth-logo">M</div>
        <div class="auth-kicker">MEDICAL AI PLATFORM</div>
        <h1>让医疗 AI<br>可治理地落地</h1>
        <p>应用工厂 · 知识治理 · 模型网关 · 评测门禁 · 患者端联动<br>服务端 Token 身份 · 全链路审计 · 医疗安全边界</p>
        <div class="auth-points">
          <div class="auth-point"><span>01</span>业务人员从模板建应用，1 天上线</div>
          <div class="auth-point"><span>02</span>未过评测门禁不得发布，双审批可追溯</div>
          <div class="auth-point"><span>03</span>模型不可用不伪造结果，高风险自动转人工</div>
        </div>
        <div class="auth-foot">MediAgent v1.1 · POC 基线（非生产/非注册）</div>
      </section>
      <section class="auth-panel">
        <div class="auth-card">
          <h2>登录工作台</h2>
          <p class="auth-sub">使用院方账号登录；演示密码均为 <code>medagent123</code></p>
          <form id="login-form">
            <label class="field"><span>用户名</span><input id="login-user" value="u_creator" autocomplete="username" /></label>
            <label class="field"><span>密码</span><input id="login-pass" type="password" value="medagent123" autocomplete="current-password" /></label>
            <button class="btn btn-primary auth-submit" type="submit">登录</button>
          </form>
          <div class="demo-title">快速切换演示角色</div>
          <div class="demo-grid">
            ${[
              ['u_creator', '业务人员'], ['u_dept', '科室审批'], ['u_platform', '平台审批'],
              ['u_knowledge', '知识运营'], ['u_eval', '评测'], ['u_patient', '患者'],
            ].map(([id, label]) => `<button type="button" class="demo-chip" data-user="${id}">
              <strong>${label}</strong><span>${id}</span></button>`).join('')}
          </div>
        </div>
      </section>
    </div>`;
  $$('.demo-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      $('#login-user').value = chip.dataset.user;
      $('#login-pass').focus();
    });
  });
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
    const params = new URLSearchParams((window.location.hash.split('?')[1] || ''));
    const keyword = (params.get('q') || '').trim();
    const list = keyword
      ? apps.items.filter((app) => `${app.name}${app.code}${app.template_name}${app.department}`.includes(keyword))
      : apps.items;
    const canCreate = has('app:create');
    view.innerHTML = `
      <div class="apps-toolbar card">
        <div>
          <h3 class="section-title" style="margin-bottom:4px">应用目录 <span class="muted small">（${list.length}/${apps.total}）</span></h3>
          <div class="section-sub" style="margin:0">从模板创建 → 试跑 → 发布检查 → 科室/平台审批 → 发布</div>
        </div>
        <div class="btn-row">
          <div class="search-box">${icon('search', 15)}<input id="apps-filter" placeholder="筛选名称 / 编号 / 科室" value="${esc(keyword)}" /></div>
          ${canCreate ? `<button class="btn btn-primary" onclick="MA.toggleCreate()">＋ 新建应用</button>` : ''}
        </div>
      </div>
      ${canCreate ? `<div class="card hidden" id="create-panel">
        <h3 class="section-title">从模板创建应用</h3>
        <p class="section-sub">模板固定提示词、知识范围、模型策略与评测门禁；创建后先试跑，再走发布检查与双审批。</p>
        <div class="form-row">
          <label class="field"><span>应用名称</span><input id="app-name" placeholder="例如：心内科知识助手" /></label>
          <label class="field"><span>模板</span><select id="app-template">
            ${state.templates.map((t) => `<option value="${esc(t.key)}">${esc(t.name)}（v${t.version} · ${esc(t.risk_level)} · 阈值 ${t.eval_threshold}）</option>`).join('')}
          </select></label>
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" onclick="MA.createApp()">创建草稿</button>
          <button class="btn btn-ghost" onclick="MA.toggleCreate()">取消</button>
        </div>
      </div>` : ''}
      <div class="app-grid">
        ${list.map((app) => `<a class="app-card" href="#/apps/${app.id}">
          <div class="app-card-top">
            <span class="app-code mono">${esc(app.code)}</span>
            ${statusPill(app.status)}
          </div>
          <div class="app-card-name">${esc(app.name)}</div>
          <div class="app-card-sub">${esc(app.template_name)} · ${esc(app.department)}</div>
          <div class="app-card-meta">
            <span>版本 <b>v${app.current_version || 0}</b></span>
            <span>门禁 ${app.latest_eval ? statusPill(app.latest_eval.gate_status) : '<span class="pill gray">未评测</span>'}</span>
          </div>
          <div class="app-card-foot">
            <span>${esc(app.owner_id)}</span>
            <span class="app-open">打开 ${icon('arrow', 14)}</span>
          </div>
        </a>`).join('') || `<div class="card empty-block">未找到匹配应用${keyword ? `（${esc(keyword)}）` : ''}</div>`}
      </div>`;
    const filter = $('#apps-filter');
    if (filter) {
      filter.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        const value = filter.value.trim();
        window.location.hash = value ? `#/apps?q=${encodeURIComponent(value)}` : '#/apps';
      });
    }
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

function toggleCreate() {
  const panel = $('#create-panel');
  if (panel) panel.classList.toggle('hidden');
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

/* ---------------------------------------------------------------- 运行调试（对话式） */
const pg = { apps: [], app: null, messages: [], sending: false };

async function renderPlayground(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const apps = await api('/api/apps');
    pg.apps = apps.items;
    const params = new URLSearchParams((window.location.hash.split('?')[1] || ''));
    const wanted = Number(params.get('app'));
    const target = apps.items.find((item) => item.id === wanted)
      || apps.items.find((item) => item.status === 'published')
      || apps.items[0];
    if (!target) {
      view.innerHTML = `<div class="card">${'暂无可用应用，请先在应用工厂创建。'}</div>`;
      return;
    }
    await pgSelect(view, target.id);
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function pgSelect(view, appId) {
  try {
    const app = await api(`/api/apps/${appId}`);
    pg.app = app;
    pg.messages = [];
    pg.sessionId = null;
    view.innerHTML = `
      <div class="pg-layout">
        <aside class="pg-side card">
          <label class="field"><span>选择应用</span>
            <select id="pg-app-select">
              ${pg.apps.map((item) => `<option value="${item.id}" ${item.id === appId ? 'selected' : ''}>${esc(item.name)}（${statusText(item.status)}）</option>`).join('')}
            </select>
          </label>
          <div class="pg-apphead">
            <div class="pg-avatar">${esc(app.template_name.slice(0, 1))}</div>
            <div>
              <div class="pg-appname">${esc(app.name)}</div>
              <div class="small muted">${esc(app.department)} · ${esc(app.template_name)}</div>
            </div>
          </div>
          <div class="pg-meta">
            <div><span>状态</span>${statusPill(app.status)}</div>
            <div><span>版本</span>v${app.current_version || 0}</div>
            <div><span>风险</span>${esc(app.risk_level)}</div>
            <div><span>模型策略</span>${esc(app.config.model_policy)}</div>
            <div><span>知识范围</span>${esc((app.config.knowledge_scope || []).join('、'))}</div>
          </div>
          <div class="btn-row" style="margin-top:14px">
            <a class="btn btn-outline btn-sm" href="#/apps/${app.id}">应用详情</a>
            <button class="btn btn-ghost btn-sm" onclick="MA.pgReset()">清空对话</button>
          </div>
          <div class="pg-quick">
            <div class="section-label">示例问题</div>
            ${pgQuickQuestions(app).map((q) => `<button class="quick-chip" data-quick="${esc(q)}">${esc(q)}</button>`).join('')}
          </div>
          <div class="pg-note small muted">试跑同样走模板→知识→模型网关→安全检查；输出含引用、版本与免责声明，不写入正式记录。</div>
        </aside>
        <section class="pg-main card">
          <div class="pg-head">
            <div>
              <div class="pg-title">${esc(app.name)} <span class="pill ${app.status === 'published' ? 'green' : 'gray'}">${statusText(app.status)}</span></div>
              <div class="small muted">${esc(app.template_name)} v${app.template_version} · 模板/提示词/模型/知识版本随输出固定</div>
            </div>
            <div class="btn-row">
              <span class="pg-model">记忆 ${esc(app.config.memory_write_mode || 'off')} / ${esc(app.config.memory_search_mode || 'vector')}</span>
              <button class="btn btn-outline btn-sm" onclick="MA.pgCloseSession()">结束会话写入摘要</button>
            </div>
          </div>
          <div class="pg-chat" id="pg-chat"></div>
          <div class="pg-composer">
            <textarea id="pg-input" rows="2" placeholder="输入问题（知识问答），或粘贴病历文本（病历质控）… Ctrl+Enter 发送"></textarea>
            <button class="btn btn-primary" id="pg-send">发送</button>
          </div>
        </section>
      </div>`;
    $('#pg-app-select').addEventListener('change', (event) => {
      const id = Number(event.target.value);
      window.location.hash = `#/playground?app=${id}`;
    });
    $('#pg-send').addEventListener('click', () => pgSend());
    $('#pg-input').addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); pgSend(); }
    });
    $$('.quick-chip').forEach((chip) => chip.addEventListener('click', () => {
      $('#pg-input').value = chip.dataset.quick;
      $('#pg-input').focus();
    }));
    pgRender();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function statusText(status) {
  return {
    draft: '草稿', testing: '测试中', pending_dept: '待科室审批', pending_platform: '待平台审批',
    published: '已发布', disabled: '已停用',
  }[status] || status;
}

function pgQuickQuestions(app) {
  if (app.template_key === 'med-qc') {
    return [
      '患者主诉胸痛 3 天，现病史不详，初步诊断待查',
      '入院记录：主诉胸痛，查体无异常，初步诊断待查',
      '出院小结缺少医师签名',
    ];
  }
  if (app.template_key === 'med-report') {
    return [
      '胸部 CT：右肺上叶结节 8mm，边界清楚',
      '腹部超声：肝实质回声增强，考虑脂肪肝',
      '胸部 CT：右肺结节，未描述大小',
    ];
  }
  return [
    '社区获得性肺炎抗感染治疗原则是什么？',
    '华法林与哪些药物相互作用？',
    '院内输血知情同意流程要求？',
  ];
}

function pgRender() {
  const chat = $('#pg-chat');
  if (!chat) return;
  if (!pg.messages.length) {
    chat.innerHTML = `<div class="pg-welcome">
      <div class="pg-welcome-icon">${icon('chat', 26)}</div>
      <div class="pg-welcome-title">开始调试「${esc(pg.app.name)}」</div>
      <div class="pg-welcome-desc">${pg.app.template_key === 'med-qc'
        ? '粘贴一段病历文本，查看质控缺陷清单（类型/依据/定位/建议）。'
        : '输入临床问题，查看带引用的回答与执行轨迹。'}</div>
      <div class="pg-welcome-meta">
        <span>${icon('shield', 13)}医生终审 · 不构成诊疗建议</span>
        <span>${icon('book', 13)}仅检索已审核生效知识</span>
      </div>
    </div>`;
    return;
  }
  chat.innerHTML = pg.messages.map((message, index) => {
    if (message.role === 'user') {
      return `<div class="msg-row user"><div class="msg-bubble">${esc(message.text)}</div></div>`;
    }
    if (message.pending) {
      return `<div class="msg-row bot"><div class="msg-bubble pending">正在执行：模板 → 知识 → 模型 → 安全检查…</div></div>`;
    }
    const result = message.result;
    return `<div class="msg-row bot">
      <div class="msg-avatar">M</div>
      <div class="msg-body">
        <div class="msg-bubble">
          <div class="msg-text">${esc(result.output)}</div>
          ${result.citations && result.citations.length
            ? `<div class="citations">${result.citations.map((c) => `<span class="citation">${esc(c.citation || c.title)}</span>`).join('')}</div>`
            : `<div class="alert amber small">无可用引用：按规则拒答或提示人工，不编造。</div>`}
          ${result.degraded ? `<div class="alert amber small">降级/阻断标记：当前输出非主模型或已触发安全处置。</div>` : ''}
        </div>
        <div class="msg-meta">
          <span>${result.latency_ms}ms · ${result.tokens} tokens</span>
          <span>模型 ${esc(result.versions.model || '—')} · 策略 ${esc(result.versions.model_policy)}</span>
          ${result.memory && result.memory.auto_written ? `<span class="pill teal">运行后自动写入记忆</span>` : ''}
          <span>免责：${esc(result.disclaimer)}</span>
        </div>
        <details class="trace">
          <summary>执行轨迹（${result.trace.length} 步）</summary>
          ${result.trace.map((step) => `<div class="trace-row">
            <span class="trace-dot ${esc(step.status)}"></span>
            <div><div class="trace-name">${esc(step.name)} <span class="pill ${traceTone(step.status)}">${esc(traceStatus(step.status))}</span></div>
            <div class="trace-detail">${esc(step.detail)} · ${step.latency_ms}ms</div></div>
          </div>`).join('')}
        </details>
        <div class="msg-actions">
          <button class="btn btn-ghost btn-sm" data-feedback="good" data-index="${index}">👍 有帮助</button>
          <button class="btn btn-ghost btn-sm" data-feedback="bad" data-index="${index}">👎 没帮助</button>
          <span class="small muted">反馈进入 BadCase 队列</span>
        </div>
      </div>
    </div>`;
  }).join('');
  chat.scrollTop = chat.scrollHeight;
  chat.querySelectorAll('[data-feedback]').forEach((button) => {
    button.addEventListener('click', () => pgFeedback(Number(button.dataset.index), button.dataset.feedback));
  });
}

function traceStatus(status) {
  return { succeeded: '完成', empty: '未命中', degraded: '降级', failed: '失败', blocked: '阻断' }[status] || status;
}
function traceTone(status) {
  return { succeeded: 'green', empty: 'amber', degraded: 'amber', failed: 'red', blocked: 'red' }[status] || 'gray';
}

async function pgSend() {
  const input = $('#pg-input');
  const text = input.value.trim();
  if (!text || pg.sending) return;
  pg.sending = true;
  pg.messages.push({ role: 'user', text });
  pg.messages.push({ role: 'assistant', pending: true });
  input.value = '';
  pgRender();
  try {
    const result = await api(`/api/apps/${pg.app.id}/trial`, { method: 'POST', body: { query: text, session_id: pg.sessionId } });
    if (result.session_id) pg.sessionId = result.session_id;
    pg.messages.pop();
    pg.messages.push({ role: 'assistant', result, question: text });
  } catch (error) {
    pg.messages.pop();
    pg.messages.push({ role: 'assistant', result: {
      output: `试跑失败：${error.message}`, citations: [], trace: [],
      latency_ms: 0, tokens: 0, degraded: true,
      versions: { model: '—', model_policy: '—' }, disclaimer: '请稍后重试',
    } });
  } finally {
    pg.sending = false;
    pgRender();
  }
}

function pgReset() {
  if (pg.app) {
    pg.messages = [];
    pgRender();
  }
}

async function pgCloseSession() {
  if (!pg.sessionId) {
    toast('请先发送一条消息（会自动创建会话）', 'error');
    return;
  }
  try {
    const result = await api(`/api/sessions/${pg.sessionId}/close`, { method: 'POST' });
    if (result.memory_id) {
      toast(`会话摘要已写入记忆 #${result.memory_id}`);
    } else {
      toast(`会话已结束（写入模式：${result.write_mode}，未写入记忆）`);
    }
    pg.sessionId = null;
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function pgFeedback(index, value) {
  const message = pg.messages[index];
  if (!message || !message.result) return;
  let reason = 'quality';
  let comment = '';
  if (value === 'bad') {
    reason = window.prompt('请选择问题类别：accuracy（准确性）/ recall（漏检）/ safety（安全）/ ux（体验）', 'accuracy') || 'accuracy';
    comment = window.prompt('补充说明（可选）') || '';
  }
  try {
    const data = await api(`/api/apps/${pg.app.id}/feedback`, {
      method: 'POST',
      body: { helpful: value === 'good', question: message.question || '', output: message.result.output, reason, comment },
    });
    toast(value === 'good' ? '感谢反馈' : `已登记 BadCase #${data.badcase_id || ''}`, value === 'good' ? '' : 'error');
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
            <a class="btn btn-outline btn-sm" href="#/playground?app=${app.id}">运行调试</a>
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
          <div class="small"><b>长期记忆：</b>${app.config.memory_enabled ? '<span class="pill green">已开启</span>' : '<span class="pill gray">未开启</span>'} · 写入 ${esc(app.config.memory_write_mode || 'off')} · 检索 ${esc(app.config.memory_search_mode || 'vector')}</div>
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
      ${canEdit && ['draft', 'testing'].includes(app.status) ? `<div class="card">
        <h3 class="section-title">记忆与运行配置</h3>
        <p class="section-sub">仅草稿/测试状态可修改；auto=每次运行后写摘要，session=结束会话时写摘要，vector=64 维向量检索。</p>
        <div class="form-row">
          <label class="field"><span>启用长期记忆</span>
            <select id="mem-enabled">
              <option value="1" ${app.config.memory_enabled ? 'selected' : ''}>开启</option>
              <option value="0" ${app.config.memory_enabled ? '' : 'selected'}>关闭</option>
            </select></label>
          <label class="field"><span>写入模式</span>
            <select id="mem-write-mode">
              ${['off', 'session', 'auto'].map((mode) => `<option value="${mode}" ${(app.config.memory_write_mode || 'off') === mode ? 'selected' : ''}>${mode}</option>`).join('')}
            </select></label>
          <label class="field"><span>检索模式</span>
            <select id="mem-search-mode">
              <option value="vector" ${(app.config.memory_search_mode || 'vector') === 'vector' ? 'selected' : ''}>向量（64 维）</option>
              <option value="bigram" ${(app.config.memory_search_mode || 'vector') === 'bigram' ? 'selected' : ''}>关键词（bigram）</option>
            </select></label>
        </div>
        <div class="form-actions"><button class="btn btn-primary btn-sm" onclick="MA.saveMemoryConfig()">保存记忆配置</button></div>
      </div>` : ''}
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

async function saveMemoryConfig() {
  const app = window.MA.currentApp;
  if (!app) return;
  try {
    await api(`/api/apps/${app.id}`, { method: 'PUT', body: {
      memory_enabled: $('#mem-enabled').value === '1',
      memory_write_mode: $('#mem-write-mode').value,
      memory_search_mode: $('#mem-search-mode').value,
    } });
    toast('记忆配置已保存');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 报告编辑 */
let reportSelected = null;

async function renderReports(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [reportData, apps] = await Promise.all([api('/api/reports?limit=100'), api('/api/apps')]);
    const reportApps = apps.items.filter((app) => app.template_key === 'med-report');
    const canWrite = has('report:write');
    let selected = reportData.items.find((item) => item.id === reportSelected) || reportData.items[0] || null;
    if (selected) reportSelected = selected.id;
    let patientContext = null;
    if (selected && selected.patient_ref) {
      try {
        patientContext = await api(`/api/integrations/patient/${encodeURIComponent(selected.patient_ref)}`);
      } catch (error) {
        patientContext = null;
      }
    }
    view.innerHTML = `
      <div class="grid grid-2">
        <div class="card">
          <h3 class="section-title">生成报告草稿</h3>
          <p class="section-sub">仅“报告初稿助手”模板可生成；输出 JSON → 医生编辑 → 签名，签名时计算修改率。</p>
          ${canWrite ? `<form id="report-form">
            <div class="form-row">
              <label class="field"><span>报告应用</span><select id="report-app">
                ${reportApps.map((app) => `<option value="${app.id}">${esc(app.name)}（${statusText(app.status)}）</option>`).join('') || '<option value="">暂无报告应用</option>'}
              </select></label>
              <label class="field"><span>检查类型</span><input id="report-exam" value="胸部 CT" /></label>
            </div>
            <div class="form-row">
              <label class="field"><span>患者标识（可选，脱敏）</span><input id="report-patient" placeholder="P0001" /></label>
            </div>
            <label class="field"><span>结构化所见 / 输入</span><textarea id="report-findings" placeholder="右肺上叶结节 8mm，边界清楚">右肺上叶结节 8mm，边界清楚</textarea></label>
            <button class="btn btn-primary" type="submit">生成草稿</button>
          </form>` : '<div class="alert amber">当前角色无报告编辑权限（可用 u_doctor / u_creator 演示）。</div>'}
        </div>
        <div class="card">
          <h3 class="section-title">报告编辑器</h3>
          ${selected ? `
            <div class="btn-row" style="justify-content:space-between;margin-bottom:10px">
              <div><strong>${esc(selected.code)}</strong> ${statusPill(selected.status)}
                <span class="small muted">${esc(selected.exam_type)} · 患者 ${esc(selected.patient_ref || '—')}</span></div>
              ${selected.status === 'signed' ? `<span class="small muted">修改率 ${selected.edit_rate !== null ? Math.round(selected.edit_rate * 100) + '%' : '—'} · 签名人 ${esc(selected.editor_id || '')}</span>` : ''}
            </div>
            ${patientContext ? `<div class="alert teal small">
              患者上下文（HIS/EMR/PACS mock）：${esc(patientContext.sex)} · ${patientContext.age} 岁 ·
              过敏：${esc((patientContext.allergies || []).join('、') || '无记录')} ·
              就诊 ${patientContext.encounters.length} 次 · 影像 ${patientContext.studies.length} 项
            </div>` : (selected.patient_ref ? '<div class="alert amber small">未获取到患者上下文（mock 仅 P0001/P0002）</div>' : '')}
            <label class="field"><span>检查所见</span><textarea id="rpt-findings" ${selected.status === 'signed' ? 'disabled' : ''}>${esc(selected.findings)}</textarea></label>
            <label class="field"><span>印象</span><textarea id="rpt-impression" ${selected.status === 'signed' ? 'disabled' : ''}>${esc(selected.impression)}</textarea></label>
            <label class="field"><span>建议</span><textarea id="rpt-recommendation" ${selected.status === 'signed' ? 'disabled' : ''}>${esc(selected.recommendation)}</textarea></label>
            ${selected.missing_fields.length ? `<div class="alert amber">缺失字段提示：${esc(selected.missing_fields.join('、'))}</div>` : ''}
            ${selected.status === 'draft' && canWrite ? `<div class="btn-row">
              <button class="btn btn-outline" onclick="MA.saveReport()">保存修改</button>
              <button class="btn btn-primary" onclick="MA.signReport()">签名生效</button>
            </div>` : `<div class="alert green">已签名：报告不可再修改，修改率已记录。</div>
            ${selected.written_back_at
              ? `<div class="alert teal small">已回写 HIS：external_id=${esc(selected.external_id)} · ${esc(selected.written_back_at)}</div>`
              : (canWrite ? '<button class="btn btn-outline btn-sm" onclick="MA.writebackReport()">回写 HIS（mock）</button>' : '')}`}
          ` : '<div class="muted small">左侧生成一份报告草稿，或从下方列表打开。</div>'}
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">报告草稿列表 <span class="muted small">（${reportData.total}）</span></h3>
        <div class="table-wrap"><table><thead><tr><th>编号</th><th>检查类型</th><th>患者</th><th>状态</th><th>修改率</th><th>创建人</th><th>时间</th><th></th></tr></thead><tbody>
          ${reportData.items.map((item) => `<tr>
            <td class="mono">${esc(item.code)}</td><td>${esc(item.exam_type)}</td><td>${esc(item.patient_ref || '—')}</td>
            <td>${statusPill(item.status === 'signed' ? 'published' : 'draft')}</td>
            <td>${item.edit_rate === null ? '—' : `${Math.round(item.edit_rate * 100)}%`}</td>
            <td class="small mono">${esc(item.created_by)}</td><td class="small muted">${esc(item.updated_at)}</td>
            <td><button class="btn btn-outline btn-sm" onclick="MA.openReport(${item.id})">打开</button></td></tr>`).join('') || '<tr><td colspan="8" class="muted">暂无报告草稿</td></tr>'}
        </tbody></table></div>
      </div>`;
    if (canWrite) {
      $('#report-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        await generateReportDraft();
      });
    }
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function generateReportDraft() {
  const appId = Number($('#report-app')?.value);
  if (!appId) { toast('请先创建报告初稿应用', 'error'); return; }
  const findings = $('#report-findings').value.trim();
  if (!findings) { toast('请输入所见', 'error'); return; }
  try {
    const report = await api('/api/reports/draft', { method: 'POST', body: {
      app_id: appId, exam_type: $('#report-exam').value.trim(), findings,
      patient_ref: $('#report-patient').value.trim(),
    } });
    reportSelected = report.id;
    toast(`已生成 ${report.code}`);
    route();
  } catch (error) { toast(error.message, 'error'); }
}

function openReport(id) {
  reportSelected = Number(id);
  route();
}

async function saveReport() {
  if (!reportSelected) return;
  try {
    await api(`/api/reports/${reportSelected}`, { method: 'PUT', body: {
      findings: $('#rpt-findings').value, impression: $('#rpt-impression').value,
      recommendation: $('#rpt-recommendation').value,
    } });
    toast('报告草稿已保存');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

async function signReport() {
  if (!reportSelected) return;
  if (!window.confirm('签名后报告不可修改，确认签名？')) return;
  try {
    const report = await api(`/api/reports/${reportSelected}/sign`, { method: 'POST' });
    toast(report.edit_rate !== null ? `签名完成，修改率 ${Math.round(report.edit_rate * 100)}%` : '签名完成');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

async function writebackReport() {
  if (!reportSelected) return;
  try {
    const result = await api('/api/integrations/report-writeback', { method: 'POST', body: { report_id: reportSelected } });
    toast(`已回写 HIS：${result.external_id}${result.idempotent ? '（幂等）' : ''}`);
    route();
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 数据集成 */
async function renderIntegrations(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [status, calls, difyStatus, difyApps] = await Promise.all([
      api('/api/integrations/status'), api('/api/integrations/calls').catch(() => ({ items: [] })),
      api('/api/integrations/dify/status').catch(() => ({ configured: false, apps: 0, detail: '未配置' })),
      api('/api/integrations/dify/apps').catch(() => ({ items: [] })),
    ]);
    const canRegisterDify = has('model:read');
    const canRunDify = has('app:trial');
    view.innerHTML = `
      <div class="grid grid-3">
        ${status.items.map((item) => `<div class="card">
          <div class="list-title">${esc(item.name.toUpperCase())} <span class="pill ${item.configured ? 'green' : 'gray'}">${item.mode}</span></div>
          <div class="small muted" style="margin-top:6px">${esc(item.detail)}</div>
        </div>`).join('')}
      </div>
      <div class="alert amber" style="margin-top:16px">${esc(status.note)}</div>
      <div class="grid grid-2" style="margin-top:20px">
        <div class="card">
          <h3 class="section-title">患者上下文查询（HIS/EMR/PACS mock）</h3>
          <div class="btn-row"><input id="integration-patient" value="P0001" placeholder="患者标识 P0001 / P0002" />
            <button class="btn btn-primary" onclick="MA.queryIntegration()">查询</button></div>
          <div id="integration-patient-result" style="margin-top:14px"></div>
        </div>
        <div class="card">
          <h3 class="section-title">集成调用记录</h3>
          <div class="table-wrap"><table><thead><tr><th>时间</th><th>集成</th><th>动作</th><th>目标</th><th>状态</th><th>external_id</th></tr></thead><tbody>
            ${calls.items.map((call) => `<tr><td class="small muted">${esc(call.created_at)}</td><td>${esc(call.integration)}</td>
              <td>${esc(call.action)}</td><td class="small">${esc(call.target)}</td><td>${statusPill(call.status)}</td>
              <td class="mono small">${esc(call.external_id || '')}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">暂无调用（在报告编辑器签名后“回写 HIS”会生成）</td></tr>'}
          </tbody></table></div>
        </div>
      </div>
      <div class="card">
        <h3 class="section-title">Dify 长尾应用（PRD v2.0 应用工厂的另一模式）</h3>
        <div class="alert ${difyStatus.configured ? 'ok' : 'amber'} small">${esc(difyStatus.detail || '未配置')} · 已登记 ${difyStatus.apps || 0} 个应用。平台不修改 Dify 源码，仅通过 API 调用。</div>
        ${canRegisterDify ? `<form id="dify-form" style="margin-top:12px">
          <div class="form-row">
            <label class="field"><span>应用名称</span><input id="dify-name" placeholder="例如：合同摘要生成（Dify）" required /></label>
            <label class="field"><span>类型</span><select id="dify-type"><option value="chat">chat</option><option value="workflow">workflow</option></select></label>
          </div>
          <div class="form-row">
            <label class="field"><span>Dify 应用地址（可选，覆盖环境变量）</span><input id="dify-base" placeholder="https://dify.example.com" /></label>
            <label class="field"><span>App ID（登记用）</span><input id="dify-appid" placeholder="app-xxxx" /></label>
          </div>
          <button class="btn btn-primary btn-sm" type="submit">登记 Dify 应用</button>
        </form>` : '<div class="small muted">仅管理/平台审批角色可登记。</div>'}
        <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>编号</th><th>名称</th><th>类型</th><th>状态</th><th>App ID</th><th>操作</th></tr></thead><tbody>
          ${difyApps.items.map((app) => `<tr><td class="mono small">${esc(app.code)}</td><td>${esc(app.name)}</td>
            <td>${esc(app.app_type)}</td><td><span class="pill ${difyStatus.configured ? 'green' : 'gray'}">${difyStatus.configured ? '可运行' : '未配置'}</span></td>
            <td class="mono small">${esc(app.app_id || '—')}</td>
            <td>${canRunDify ? `<button class="btn btn-outline btn-sm" onclick="MA.runDify(${app.id})">测试运行</button>` : '—'}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">暂无登记（种子含 1 个示例）</td></tr>'}
        </tbody></table></div>
        <div id="dify-result" style="margin-top:12px"></div>
      </div>`;
    $('#integration-patient').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') queryIntegration();
    });
    const difyForm = $('#dify-form');
    if (difyForm) {
      difyForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
          await api('/api/integrations/dify/apps', { method: 'POST', body: {
            name: $('#dify-name').value.trim(), base_url: $('#dify-base').value.trim(),
            app_id: $('#dify-appid').value.trim(), app_type: $('#dify-type').value,
          } });
          toast('Dify 应用已登记');
          route();
        } catch (error) { toast(error.message, 'error'); }
      });
    }
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function runDify(id) {
  const query = window.prompt('输入发给 Dify 应用的内容（需配置 DIFY_BASE_URL/DIFY_API_KEY）');
  if (!query) return;
  const box = $('#dify-result');
  if (box) box.innerHTML = '<div class="muted small">调用中…</div>';
  try {
    const result = await api(`/api/integrations/dify/apps/${id}/run`, { method: 'POST', body: { query } });
    if (box) {
      box.innerHTML = `<div class="alert ok">Dify ${esc(result.app_type)} 调用成功 · ${result.tokens} tokens · ${result.latency_ms}ms</div>
        <div class="pre">${esc(result.answer)}</div>`;
    }
    toast('Dify 调用成功');
  } catch (error) {
    if (box) box.innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
    toast(error.message, 'error');
  }
}

async function queryIntegration() {
  const ref = ($('#integration-patient')?.value || '').trim().toUpperCase();
  const box = $('#integration-patient-result');
  if (!ref) return;
  try {
    const data = await api(`/api/integrations/patient/${encodeURIComponent(ref)}`);
    box.innerHTML = `
      <div class="alert teal">${esc(data.name_mask)} · ${esc(data.sex)} · ${data.age} 岁 · 过敏：${esc((data.allergies || []).join('、') || '无记录')}</div>
      <div class="small"><b>就诊记录</b></div>
      <div class="table-wrap" style="margin:8px 0 14px"><table><thead><tr><th>时间</th><th>科室</th><th>医生</th><th>诊断/状态</th></tr></thead><tbody>
        ${data.encounters.map((item) => `<tr><td>${esc(item.date)}</td><td>${esc(item.department)}</td><td>${esc(item.doctor)}</td><td>${esc(item.diagnosis)} · ${esc(item.status)}</td></tr>`).join('')}
      </tbody></table></div>
      <div class="small"><b>影像检查</b></div>
      <div class="table-wrap" style="margin-top:8px"><table><thead><tr><th>检查号</th><th>日期</th><th>模态</th><th>部位</th><th>报告</th></tr></thead><tbody>
        ${data.studies.map((item) => `<tr><td class="mono small">${esc(item.study_id)}</td><td>${esc(item.date)}</td><td>${esc(item.modality)}</td><td>${esc(item.body_part)}</td><td>${esc(item.report_status)}</td></tr>`).join('')}
      </tbody></table></div>
      <div class="small muted" style="margin-top:8px">来源：${esc((data.sources || []).join(' / '))} · 合成脱敏数据</div>`;
  } catch (error) {
    box.innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
  }
}

/* ---------------------------------------------------------------- 知识中心 */
async function renderKnowledge(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const [data, faqData] = await Promise.all([
      api('/api/knowledge?limit=100'), api('/api/faqs?limit=100'),
    ]);
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
      </div>
      <div class="card">
        <div class="btn-row" style="justify-content:space-between">
          <div>
            <h3 class="section-title" style="margin-bottom:4px">FAQ（旧版知识库能力吸收）</h3>
            <div class="section-sub" style="margin:0">已审核 FAQ 参与知识检索；待审核不生效。</div>
          </div>
          ${canWrite ? '<button class="btn btn-primary btn-sm" onclick="MA.toggleFaqForm()">＋ 新建 FAQ</button>' : ''}
        </div>
        ${canWrite ? `<form id="faq-form" class="hidden" style="margin-top:12px">
          <div class="form-row">
            <label class="field"><span>问题</span><input id="faq-question" required /></label>
            <label class="field"><span>来源</span><input id="faq-source" value="院内 FAQ" /></label>
          </div>
          <label class="field"><span>回答</span><textarea id="faq-answer" required></textarea></label>
          <label class="field"><span>适用范围（逗号分隔）</span><input id="faq-scope" value="公共" /></label>
          <button class="btn btn-primary" type="submit">提交审核</button>
        </form>` : ''}
        <div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>问题</th><th>回答</th><th>范围</th><th>来源</th><th>状态</th><th>操作</th></tr></thead><tbody>
          ${(faqData.items || []).map((faq) => `<tr>
            <td><strong>${esc(faq.question)}</strong></td>
            <td class="small">${esc(faq.answer)}</td>
            <td class="small">${(faq.scope || []).join('、')}</td>
            <td class="small">${esc(faq.source)}</td>
            <td>${statusPill(faq.status)}</td>
            <td>${faq.status === 'pending' && canReview ? `<button class="btn btn-ok btn-sm" onclick="MA.reviewFaq(${faq.id},'approve')">通过</button>
              <button class="btn btn-danger btn-sm" onclick="MA.reviewFaq(${faq.id},'reject')">拒绝</button>` : '<span class="muted small">—</span>'}</td>
          </tr>`).join('') || '<tr><td colspan="6" class="muted">暂无 FAQ</td></tr>'}
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
      const faqForm = $('#faq-form');
      if (faqForm) {
        faqForm.addEventListener('submit', async (event) => {
          event.preventDefault();
          try {
            await api('/api/faqs', { method: 'POST', body: {
              question: $('#faq-question').value.trim(), answer: $('#faq-answer').value.trim(),
              source: $('#faq-source').value.trim(),
              scope: $('#faq-scope').value.split(',').map((s) => s.trim()).filter(Boolean),
            } });
            toast('FAQ 已提交审核');
            route();
          } catch (error) { toast(error.message, 'error'); }
        });
      }
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

function toggleFaqForm() {
  const form = $('#faq-form');
  if (form) form.classList.toggle('hidden');
}

async function reviewFaq(id, decision) {
  const comment = decision === 'approve' ? 'FAQ 审核通过' : (window.prompt('拒绝原因（必填）') || '');
  if (decision === 'reject' && !comment) return;
  try {
    await api(`/api/faqs/${id}/review`, { method: 'POST', body: { decision, comment } });
    toast(decision === 'approve' ? 'FAQ 已通过' : 'FAQ 已拒绝');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

/* ---------------------------------------------------------------- 记忆 */
const MEMORY_SCOPE_LABELS = { user: '用户', agent: '应用', tenant: '租户' };
const MEMORY_TYPE_LABELS = { preference: '偏好', fact: '事实', summary: '摘要', instruction: '指令' };

async function renderMemory(view) {
  view.innerHTML = '<div class="card">加载中…</div>';
  try {
    const data = await api('/api/memories?limit=100');
    const canWrite = has('memory:write');
    const canHard = has('admin');
    view.innerHTML = `
      <div class="grid grid-4">
        ${kpi('记忆总数', data.stats.total, '含已删除', 'teal')}
        ${kpi('活跃记忆', data.stats.active, '参与试跑注入', 'green')}
        ${kpi('累计使用', data.stats.total_use, '被注入次数', 'amber')}
        ${kpi('向量化', `${data.stats.with_embedding || 0}/${data.stats.total}`, `${data.embedding_dim || 64} 维 bigram 向量`, 'violet')}
      </div>
      <div class="grid grid-2" style="margin-top:20px">
        ${canWrite ? `<div class="card">
          <h3 class="section-title">新建记忆</h3>
          <p class="section-sub">范围：用户（本账号）/ 应用（指定应用 ID）/ 租户（default）；相同 scope+owner+type+content 自动去重。</p>
          <form id="memory-form">
            <div class="form-row">
              <label class="field"><span>范围</span><select id="mem-scope">
                <option value="user">用户（user）</option>
                <option value="agent">应用（agent）</option>
                <option value="tenant">租户（tenant）</option>
              </select></label>
              <label class="field"><span>owner（user/agent 时填写）</span><input id="mem-owner" placeholder="应用 ID；用户默认本人" /></label>
            </div>
            <div class="form-row">
              <label class="field"><span>类型</span><select id="mem-type">
                ${Object.entries(MEMORY_TYPE_LABELS).map(([k, label]) => `<option value="${k}">${label}</option>`).join('')}
              </select></label>
              <label class="field"><span>重要度（1–3）</span><input id="mem-importance" type="number" min="1" max="3" value="2" /></label>
            </div>
            <label class="field"><span>内容</span><textarea id="mem-content" placeholder="例如：回答时先给结论，再列引用依据。" required></textarea></label>
            <label class="field"><span>过期时间（可选）</span><input id="mem-expires" placeholder="2027-10-01T00:00:00+08:00" /></label>
            <button class="btn btn-primary" type="submit">创建记忆</button>
          </form>
        </div>` : `<div class="card"><div class="alert amber">当前角色无记忆写入权限（可用 u_doctor / u_creator / u_knowledge 演示）。</div></div>`}
        <div class="card">
          <h3 class="section-title">试跑时的注入规则</h3>
          <div class="small muted" style="line-height:1.9">
            1. 仅当应用配置 <code>memory_enabled=true</code> 时注入；<br>
            2. 检索 user=当前用户、agent=当前应用、tenant=default 的活跃且未过期记忆；<br>
            3. 按查询词相关性 + 重要度排序取 Top3，输出以「结合历史记忆」标注；<br>
            4. 注入写入执行轨迹（memory 步骤）并累计 use_count；<br>
            5. 患者端不使用临床记忆；记忆不替代医生判断。
          </div>
          <div class="alert teal small">旧 AgentHub v1.2 的记忆能力已在新中台重建：三级范围 × 四类、去重、软删/硬删、注入轨迹。</div>
        </div>
      </div>
      <div class="card">
        <div class="btn-row" style="justify-content:space-between;margin-bottom:12px">
          <h3 class="section-title" style="margin:0">记忆清单 <span class="muted small">（${data.total}）</span></h3>
          <div class="btn-row">
            <select id="mem-mode" style="width:130px">
              <option value="vector">向量（64 维）</option>
              <option value="bigram">关键词（bigram）</option>
            </select>
            <div class="search-box">${icon('search', 15)}<input id="mem-filter" placeholder="检索记忆，回车" /></div>
            <button class="btn btn-outline btn-sm" onclick="MA.searchMemory()">检索</button>
          </div>
        </div>
        <div id="mem-search-result"></div>
        <div class="table-wrap"><table><thead><tr><th>范围</th><th>类型</th><th>内容</th><th>owner</th><th>重要度</th><th>使用</th><th>状态</th><th>操作</th></tr></thead><tbody>
          ${data.items.map((item) => `<tr data-content="${esc(item.content)}">
            <td><span class="pill teal">${MEMORY_SCOPE_LABELS[item.scope] || item.scope}</span></td>
            <td class="small">${MEMORY_TYPE_LABELS[item.type] || item.type}</td>
            <td class="small" style="max-width:420px">${esc(item.content)}</td>
            <td class="mono small">${esc(item.owner)}</td>
            <td>${'★'.repeat(item.importance || 1)}</td>
            <td>${item.use_count}</td>
            <td>${statusPill(item.status === 'active' ? 'active' : 'disabled')}</td>
            <td>${canWrite ? `<button class="btn btn-outline btn-sm" onclick="MA.memoryToggle(${item.id}, '${item.status === 'active' ? 'deleted' : 'active'}')">${item.status === 'active' ? '停用' : '启用'}</button>
              <button class="btn btn-danger btn-sm" onclick="MA.memoryDelete(${item.id}, false)">删除</button>
              ${canHard ? `<button class="btn btn-ghost btn-sm" onclick="MA.memoryDelete(${item.id}, true)">硬删</button>` : ''}` : '—'}</td>
          </tr>`).join('') || '<tr><td colspan="8" class="muted">暂无记忆</td></tr>'}
        </tbody></table></div>
      </div>`;
    if (canWrite) {
      $('#memory-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
          await api('/api/memories', { method: 'POST', body: {
            scope: $('#mem-scope').value,
            owner: $('#mem-owner').value.trim(),
            type: $('#mem-type').value,
            content: $('#mem-content').value.trim(),
            importance: Number($('#mem-importance').value || 2),
            expires_at: $('#mem-expires').value.trim(),
          } });
          toast('记忆已创建');
          route();
        } catch (error) { toast(error.message, 'error'); }
      });
    }
    const filter = $('#mem-filter');
    if (filter) {
      filter.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') searchMemory();
      });
    }
  } catch (error) {
    view.innerHTML = `<div class="card alert red">${esc(error.message)}</div>`;
  }
}

async function searchMemory() {
  const query = ($('#mem-filter')?.value || '').trim();
  const mode = $('#mem-mode')?.value || 'vector';
  const box = $('#mem-search-result');
  if (!query) { if (box) box.innerHTML = ''; return; }
  try {
    const data = await api(`/api/memories/search?q=${encodeURIComponent(query)}&mode=${mode}`);
    if (!box) return;
    box.innerHTML = data.items.length
      ? `<div class="alert teal small">${mode === 'vector' ? '64 维 bigram 向量余弦 + 关键词加权' : '关键词 bigram'} · 命中 ${data.total} 条</div>
        ${data.items.map((item) => `<div class="list-item"><div class="list-main">
          <div class="list-title">${esc(item.content)}</div>
          <div class="list-sub">${MEMORY_SCOPE_LABELS[item.scope] || item.scope} · ${MEMORY_TYPE_LABELS[item.type] || item.type} · owner ${esc(item.owner)} · 相关度 ${item.score}</div>
        </div><div class="list-actions"><span class="pill teal">${item.score}</span></div></div>`).join('')}`
      : `<div class="alert amber">未命中记忆（向量/关键词均低于阈值）。</div>`;
  } catch (error) {
    if (box) box.innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
  }
}

async function memoryToggle(id, status) {
  try {
    await api(`/api/memories/${id}`, { method: 'PUT', body: { status } });
    toast(status === 'active' ? '已启用' : '已停用');
    route();
  } catch (error) { toast(error.message, 'error'); }
}

async function memoryDelete(id, hard) {
  if (!window.confirm(hard ? '硬删除后不可恢复，确认？' : '确认删除（软删）？')) return;
  try {
    await api(`/api/memories/${id}${hard ? '?hard=1' : ''}`, { method: 'DELETE' });
    toast(hard ? '已硬删除' : '已删除');
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
    const [metrics, badcases, events, handoffs, runs, alerts, costs, channels] = await Promise.all([
      api('/api/ops/metrics'), api('/api/badcases'), api('/api/safety/events').catch(() => ({ items: [] })),
      api('/api/handoffs').catch(() => ({ items: [] })), api('/api/runs?limit=20').catch(() => ({ items: [] })),
      api('/api/ops/alerts').catch(() => ({ items: [] })), api('/api/ops/costs').catch(() => null),
      api('/api/ops/notify/channels').catch(() => ({ items: [] })),
    ]);
    const m = metrics.values;
    const canManage = has('badcase:manage');
    const canNotify = has('model:read');
    view.innerHTML = `
      <div class="grid grid-4">
        ${kpi('模型调用', m.model_calls, `降级率 ${pct(m.degrade_rate)}`, 'teal')}
        ${kpi('模型 P95', `${m.p95_latency_ms}ms`, '模型耗时', 'green')}
        ${kpi('未闭环 BadCase', m.badcase_open, '需分派/关闭', 'amber')}
        ${kpi('高风险事件', m.safety_high, '阻断项', 'red')}
      </div>
      <div class="card">
        <h3 class="section-title">运营告警</h3>
        ${alerts.items.length ? alerts.items.map((item) => `<div class="list-item">
          <div class="list-main"><div class="list-title">${esc(item.title)} <span class="pill ${item.severity === 'high' ? 'red' : item.severity === 'medium' ? 'amber' : 'gray'}">${esc(item.severity)}</span></div>
          <div class="list-sub">${esc(item.detail)} · 建议：${esc(item.action)}</div></div></div>`).join('')
          : '<div class="alert green">当前无告警。</div>'}
        <div class="small muted" style="margin-top:8px">规则：高风险事件、BadCase 积压、评测通过率、模型降级/失败、知识待审核。</div>
      </div>
      <div class="card">
        <h3 class="section-title">告警通知渠道（企业微信/钉钉）</h3>
        <p class="section-sub">webhook 地址只从环境变量读取（如 ALERT_WEBHOOK_URL），不在页面展示；未配置渠道不发送。</p>
        <div class="table-wrap"><table><thead><tr><th>渠道</th><th>类型</th><th>环境变量</th><th>配置状态</th><th>操作</th></tr></thead><tbody>
          ${channels.items.map((channel) => `<tr><td>${esc(channel.name)}</td><td>${esc(channel.kind)}</td>
            <td class="mono small">${esc(channel.webhook_env)}</td>
            <td><span class="pill ${channel.configured ? 'green' : 'gray'}">${channel.configured ? '已配置' : '未配置'}</span></td>
            <td>${canNotify ? `<button class="btn btn-outline btn-sm" onclick="MA.notifyTestChannel(${channel.id})">测试发送</button>` : '—'}</td></tr>`).join('') || '<tr><td colspan="5" class="muted">暂无渠道</td></tr>'}
        </tbody></table></div>
        ${canNotify ? `<div class="btn-row" style="margin-top:12px">
          <button class="btn btn-primary btn-sm" onclick="MA.notifyAlerts()">发送当前告警到已配置渠道</button>
        </div>` : ''}
        <div id="notify-result" style="margin-top:10px"></div>
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
        <h3 class="section-title">成本对账（近 30 天）</h3>
        ${costs ? `<div class="grid grid-3">
          ${kpi('总成本', `¥${(costs.total.cost || 0).toFixed(4)}`, `${costs.total.runs} 次运行`, 'teal')}
          ${kpi('总 tokens', costs.total.tokens, `${costs.total.model_calls} 次模型调用`, 'green')}
          ${kpi('模型成本', `¥${(costs.total.model_cost || 0).toFixed(4)}`, '模型调用记录估算', 'amber')}
        </div>
        <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>应用</th><th>运行</th><th>tokens</th><th>成本</th></tr></thead><tbody>
          ${costs.by_app.map((item) => `<tr><td>${esc(item.app_name || `#${item.app_id}`)}</td><td>${item.runs}</td>
            <td>${item.tokens}</td><td>¥${(item.cost || 0).toFixed(4)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">暂无运行成本</td></tr>'}
        </tbody></table></div>
        <div class="small muted" style="margin-top:8px">${esc(costs.note)}</div>` : '<div class="muted small">暂无成本数据</div>'}
      </div>
      <div class="card">
        <h3 class="section-title">试跑运行记录（旧版运行记录能力吸收）</h3>
        <div class="table-wrap"><table><thead><tr><th>ID</th><th>应用</th><th>用户</th><th>输入</th><th>降级</th><th>记忆写入</th><th>时间</th></tr></thead><tbody>
          ${runs.items.length ? runs.items.map((run) => `<tr><td>#${run.id}</td><td>${esc(run.app_name || run.app_id)}</td>
            <td class="mono small">${esc(run.user_id)}</td><td class="small">${esc(String(run.input || '').slice(0, 40))}</td>
            <td>${run.degraded ? '<span class="pill amber">降级</span>' : '<span class="pill green">正常</span>'}</td>
            <td>${run.memory_written ? '<span class="pill teal">已写入</span>' : '—'}</td>
            <td class="small muted">${esc(run.created_at)}</td></tr>`).join('') : '<tr><td colspan="7" class="muted">暂无运行记录</td></tr>'}
        </tbody></table></div>
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

async function notifyTestChannel(id) {
  const box = $('#notify-result');
  if (box) box.innerHTML = '<div class="muted small">发送中…</div>';
  try {
    const result = await api(`/api/ops/notify/channels/${id}/test`, { method: 'POST' });
    if (box) box.innerHTML = `<div class="alert ok">测试发送成功：${esc(result.channel)}（${esc(result.kind)}）</div>`;
    toast('测试通知已发送');
  } catch (error) {
    if (box) box.innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
  }
}

async function notifyAlerts() {
  const box = $('#notify-result');
  if (box) box.innerHTML = '<div class="muted small">发送中…</div>';
  try {
    const result = await api('/api/ops/alerts/notify', { method: 'POST' });
    if (box) box.innerHTML = `<div class="alert ok">已发送 ${result.sent.length} 个渠道，包含 ${result.alerts} 条告警。</div>`;
    toast('告警通知已发送');
  } catch (error) {
    if (box) box.innerHTML = `<div class="alert red">${esc(error.message)}</div>`;
  }
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
  createApp, submitApp, decide, rollback, disableApp, saveMemoryConfig, trial,
  toggleCreate, pgReset,
  pgCloseSession, searchMemory,
  memoryToggle, memoryDelete,
  searchKnowledge, reviewDoc, reviewFaq, toggleFaqForm, testPolicy, runEval, showEvalRun,
  generateReportDraft, openReport, saveReport, signReport, writebackReport, queryIntegration, runDify,
  notifyTestChannel, notifyAlerts,
  assignBadcase, closeBadcase, loadAudit, exportAudit,
  bindPatient, revokePatient, submitFollowup,
};

const globalSearch = $('#global-search');
if (globalSearch) {
  globalSearch.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    const value = globalSearch.value.trim();
    window.location.hash = value ? `#/apps?q=${encodeURIComponent(value)}` : '#/apps';
  });
}
const searchIcon = $('#search-icon');
if (searchIcon) searchIcon.innerHTML = icon('search', 15);

$('#logout').addEventListener('click', () => logout());
window.addEventListener('hashchange', route);
route();
