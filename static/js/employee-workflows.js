/* Employee self-service workflows. All record content is rendered as text. */
(() => {
  const top = document.querySelector('.portal-top-nav-right');
  const grid = document.querySelector('.employee-grid');
  if (!top || !grid) return;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'portal-tab portal-icon-btn';
  button.dataset.panel = 'workflowsPanel';
  button.setAttribute('aria-label', 'Requests and notifications');
  button.title = 'Requests and notifications';
  button.textContent = '✉';
  button.style.position = 'relative';
  const badge = document.createElement('span');
  badge.className = 'segment-badge';
  badge.style.cssText = 'position:absolute;top:-7px;right:-7px;min-width:18px;font-size:10px;';
  badge.setAttribute('aria-live', 'polite');
  button.append(' ', badge);
  top.prepend(button);

  const panel = document.createElement('article');
  panel.className = 'portal-panel';
  panel.id = 'workflowsPanel';
  panel.innerHTML = `
    <div class="portal-card">
      <div class="portal-card-header"><h2 class="portal-card-title">Requests &amp; notifications</h2>
        <div class="portal-card-subtitle">Follow your requests, payroll and updates.</div></div>
      <div class="workflow-tabs" role="group" aria-label="Choose an area">
        <button type="button" data-area="notifications">Inbox</button>
        <button type="button" data-area="claims">Expense claims</button>
        <button type="button" data-area="grievances">Grievances</button>
        <button type="button" data-area="payroll">Payroll</button>
      </div>
      <div class="employee-status-banner" role="status" style="display:none"></div>
      <div id="workflowContent" aria-live="polite"></div>
    </div>`;
  grid.append(panel);
  const style = document.createElement('style');
  style.textContent = `.workflow-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.workflow-tabs button,.workflow-action{border:1px solid var(--employee-line);border-radius:10px;background:var(--employee-card-bg);color:var(--employee-navy);padding:10px 12px;cursor:pointer;font:inherit}.workflow-tabs button[aria-pressed="true"]{background:var(--employee-primary-btn-bg,#0284c7);color:white}.workflow-list{display:grid;gap:10px;margin-top:16px}.workflow-record{border:1px solid var(--employee-line);border-radius:12px;padding:14px;overflow-wrap:anywhere}.workflow-record p{margin:6px 0}.workflow-record button{margin-top:8px}.workflow-form{display:grid;gap:12px;margin:16px 0}.workflow-form label{display:grid;gap:5px}.workflow-detail{margin-top:16px}.workflow-unread{font-weight:700}.workflow-actions{display:flex;flex-wrap:wrap;gap:8px} .workflow-action:disabled{opacity:.6;cursor:wait}`;
  document.head.append(style);
  const content = panel.querySelector('#workflowContent');
  const status = panel.querySelector('[role=status]');
  let activeArea = 'notifications';
  let notificationLoading = false;
  let notifications = [];
  let renderVersion = 0;

  function message(text, error = false) {
    status.textContent = text;
    status.className = 'employee-status-banner ' + (error ? 'is-error' : 'is-success');
    status.style.display = text ? 'block' : 'none';
  }
  async function request(url, options) {
    const response = await portalFetch(url, options);
    const data = await payload(response);
    if (!response.ok) throw new Error(apiErrorMessage(data, 'The request could not be completed.'));
    return data;
  }
  async function getAll(url) {
    const result = [];
    let next = url;
    while (next) {
      const parsed = new URL(next, location.origin);
      if (parsed.origin !== location.origin || !parsed.pathname.startsWith('/api/')) throw new Error('Invalid page link.');
      const data = await request(parsed.pathname + parsed.search);
      result.push(...(Array.isArray(data) ? data : (data.results || [])));
      next = Array.isArray(data) ? null : data.next;
    }
    return result;
  }
  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function action(label, handler) {
    const el = node('button', label, 'workflow-action');
    el.type = 'button';
    el.addEventListener('click', async () => {
      el.disabled = true;
      try { await handler(); } finally { el.disabled = false; }
    });
    return el;
  }
  function field(form, label, name, type = 'text') {
    const wrap = node('label', label);
    const input = document.createElement(type === 'textarea' ? 'textarea' : 'input');
    if (type !== 'textarea') input.type = type;
    input.name = name;
    input.required = true;
    input.className = type === 'textarea' ? 'portal-textarea' : 'portal-input';
    if (type === 'number') { input.min = '0.01'; input.step = '0.01'; }
    wrap.append(input);
    form.append(wrap);
  }
  function addForm(area) {
    const form = node('form', null, 'workflow-form');
    field(form, 'Title', 'title');
    field(form, 'Category', 'category');
    if (area === 'claims') field(form, 'Amount', 'amount', 'number');
    else field(form, 'Details', 'details', 'textarea');
    const submit = node('button', area === 'claims' ? 'Submit claim' : 'Submit grievance', 'btn-primary-cta');
    submit.type = 'submit';
    form.append(submit);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      submit.disabled = true;
      message('');
      try {
        const values = Object.fromEntries(new FormData(form));
        if (area === 'claims' && !(Number(values.amount) > 0)) throw new Error('Enter an amount greater than zero.');
        await request(area === 'claims' ? '/api/expense-claims/' : '/api/grievances/', { method: 'POST', body: JSON.stringify(values) });
        await showArea(area);
        message(area === 'claims' ? 'Expense claim submitted.' : 'Grievance submitted.');
      } catch (error) { message(error.message, true); }
      finally { submit.disabled = false; }
    });
    content.append(form);
  }
  const fields = {
    claim: [['Title','title'],['Category','category'],['Amount','amount'],['Status','status']],
    complaint: [['Subject','subject'],['Category','category'],['Details','description'],['Status','status'],['Resolution','resolution']],
    grievance: [['Title','title'],['Category','category'],['Details','details'],['Status','status'],['Resolution','resolution']],
    payroll: [['Payroll run','payroll_run'],['Base pay','base_pay'],['Deductions','deductions'],['Net pay','net_pay']],
    leave: [['Leave type','leave_type'],['Start','start_date'],['End','end_date'],['Status','status'],['Reason','reason']],
    shift: [['Date','work_date'],['Start','start_time'],['End','end_time'],['Shift','shift_type'],['Break (minutes)','break_mins']]
  };
  const endpoints = { claim:'expense-claims', complaint:'complaints', grievance:'grievances', payroll:'payroll-items', leave:'leaves', shift:'shift-rosters' };
  function record(type, item) {
    const card = node('div', null, 'workflow-record');
    for (const [label, key] of fields[type]) {
      if (item[key] == null || item[key] === '') continue;
      const line = node('p');
      line.append(node('strong', label + ': '), document.createTextNode(String(item[key])));
      card.append(line);
    }
    return card;
  }
  async function openDetail(type, id) {
    if (!endpoints[type] || !/^[\w-]+$/.test(String(id))) return;
    switchPortalTab('workflowsPanel');
    activeArea = '';
    renderVersion++;
    updateTabs();
    content.replaceChildren(node('p', 'Loading record…'));
    message('');
    try {
      const item = await request(`/api/${endpoints[type]}/${encodeURIComponent(id)}/`);
      const heading = node('h3', type.charAt(0).toUpperCase() + type.slice(1) + ' details');
      content.replaceChildren(heading, record(type, item), action('Back to inbox', () => showArea('notifications')));
    } catch (error) { content.replaceChildren(); message(error.message, true); }
  }
  function updateTabs() {
    panel.querySelectorAll('[data-area]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.area === activeArea)));
  }
  async function refreshNotifications() {
    if (notificationLoading) return;
    notificationLoading = true;
    try {
      notifications = await getAll('/api/notifications/');
      const unread = notifications.filter(item => !item.is_read).length;
      badge.textContent = String(unread);
      button.setAttribute('aria-label', `Requests and notifications, ${unread} unread`);
      if (activeArea === 'notifications' && panel.classList.contains('active')) renderNotifications();
    } catch (error) {
      if (activeArea === 'notifications' && panel.classList.contains('active')) message(error.message, true);
    } finally { notificationLoading = false; }
  }
  function renderNotifications() {
    content.replaceChildren(node('h3', 'Inbox'));
    const list = node('div', null, 'workflow-list');
    if (!notifications.length) list.append(node('p', 'No notifications.'));
    for (const item of notifications) {
      const card = node('div', null, 'workflow-record');
      card.append(node('p', item.text, item.is_read ? '' : 'workflow-unread'));
      if (item.created_at) card.append(node('p', new Date(item.created_at).toLocaleString()));
      const actions = node('div', null, 'workflow-actions');
      const markRead = async () => {
        if (item.is_read) return true;
        try {
          await request(`/api/notifications/${encodeURIComponent(item.id)}/read/`, {method:'PATCH'});
          item.is_read = true;
          const unread = notifications.filter(note => !note.is_read).length;
          badge.textContent = String(unread);
          button.setAttribute('aria-label', `Requests and notifications, ${unread} unread`);
          return true;
        } catch (error) { message(error.message, true); return false; }
      };
      if (!item.is_read) actions.append(action('Mark read', async () => { if (await markRead()) renderNotifications(); }));
      const aliases = {expense_claim:'claim', expense:'claim', payroll_item:'payroll', shift_roster:'shift', leave_request:'leave'};
      const type = aliases[item.target_type] || item.target_type;
      if (endpoints[type] && item.target_id) actions.append(action('View details', async () => { if (await markRead()) await openDetail(type, item.target_id); }));
      card.append(actions);
      list.append(card);
    }
    content.append(list);
  }
  async function showArea(area) {
    activeArea = area;
    const version = ++renderVersion;
    updateTabs();
    message('');
    if (area === 'notifications') { renderNotifications(); await refreshNotifications(); return; }
    const types = {claims:'claim', grievances:'grievance', payroll:'payroll'};
    const type = types[area];
    content.replaceChildren(node('h3', {claims:'Expense claims', grievances:'Grievances', payroll:'Finalized payroll'}[area]));
    if (area !== 'payroll') addForm(area);
    const list = node('div', 'Loading records…', 'workflow-list');
    content.append(list);
    try {
      const items = await getAll(`/api/${endpoints[type]}/`);
      if (version !== renderVersion) return;
      list.replaceChildren();
      if (!items.length) list.append(node('p', 'No records yet.'));
      for (const item of items) {
        const card = record(type, item);
        card.append(action('View details', () => openDetail(type, item.id)));
        list.append(card);
      }
    } catch (error) { if (version === renderVersion) { list.replaceChildren(); message(error.message, true); } }
  }
  button.addEventListener('click', () => { switchPortalTab('workflowsPanel'); showArea('notifications'); });
  panel.querySelectorAll('[data-area]').forEach(el => el.addEventListener('click', () => showArea(el.dataset.area)));
  document.getElementById('complaintRows').addEventListener('click', event => {
    const target = event.target.closest('[data-complaint-detail]');
    if (target) openDetail('complaint', target.dataset.complaintDetail);
  });
  refreshNotifications();
  setInterval(() => { if (!document.hidden) refreshNotifications(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshNotifications(); });
})();
