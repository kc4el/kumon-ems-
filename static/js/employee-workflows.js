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
        <div class="portal-card-subtitle">Follow your requests and updates.</div></div>
      <div class="workflow-tabs" role="group" aria-label="Choose an area">
        <button type="button" data-area="notifications">Inbox</button>
        <button type="button" data-area="schedule">My schedule</button>
        <button type="button" data-area="swaps">Shift swaps</button>
        <button type="button" data-area="corrections">Attendance corrections</button>
        <button type="button" data-area="overtime">Overtime</button>
        <button type="button" data-area="claims">Expense claims</button>
        <button type="button" data-area="grievances">Grievances</button>
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
    leave: [['Leave type','leave_type'],['Start','start_date'],['End','end_date'],['Status','status'],['Reason','reason']],
    shift: [['Date','work_date'],['Start','start_time'],['End','end_time'],['Shift','shift_type'],['Break (minutes)','break_mins']],
    swap: [['Your shift','requester_roster'],['Other shift','target_roster'],['Reason','reason'],['Status','status']],
    correction: [['Attendance','attendance'],['Proposed clock in','proposed_clock_in'],['Proposed clock out','proposed_clock_out'],['Reason','reason'],['Status','status']],
    overtime: [['Date','date'],['Hours','hours'],['Multiplier','multiplier'],['Status','status']]
  };
  const endpoints = { claim:'expense-claims', complaint:'complaints', grievance:'grievances', leave:'leaves', shift:'shift-rosters', swap:'shift-swaps', correction:'attendance-corrections', overtime:'overtime' };
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
      if (type === 'swap') { for (const key of ['requester_roster','target_roster']) { const shift = item[`${key}_display`]; if (shift) item[key] = `${item[key === 'requester_roster' ? 'requester_employee_name' : 'target_employee_name'] || shift.employee_name} · ${shiftLabel(shift)}`; } }
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
      const aliases = {expense_claim:'claim', expense:'claim', shift_roster:'shift', leave_request:'leave', shift_swap:'swap', attendance_correction:'correction', overtime_slip:'overtime'};
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
    if (['schedule','swaps','corrections','overtime'].includes(area)) { await showStaffArea(area, version); return; }
    const types = {claims:'claim', grievances:'grievance'};
    const type = types[area];
    content.replaceChildren(node('h3', {claims:'Expense claims', grievances:'Grievances'}[area]));
    addForm(area);
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

  const dateKey = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const shiftLabel = r => `${r.work_date} · ${r.start_time || ''}–${r.end_time || ''} ${r.shift_type || ''}`;
  const attendanceLabel = a => `${a.date} · ${a.clock_in ? new Date(a.clock_in).toLocaleString() : 'No clock in'} – ${a.clock_out ? new Date(a.clock_out).toLocaleString() : 'No clock out'}`;
  function selectField(form, label, name, options) {
    const wrap = node('label', label); const select = document.createElement('select');
    select.name = name; select.required = true; select.className = 'portal-input';
    select.add(new Option('Select...', ''));
    options.forEach(([value, text]) => select.add(new Option(text, value)));
    wrap.append(select); form.append(wrap); return select;
  }
  function submitForm(form, endpoint, build, area) {
    const submit = node('button', 'Submit request', 'btn-primary-cta'); submit.type = 'submit'; form.append(submit);
    form.onsubmit = async event => {
      event.preventDefault(); if (!form.reportValidity()) return;
      submit.disabled = true; message('');
      try { await request(endpoint, {method:'POST', body:JSON.stringify(build(new FormData(form)))}); await showArea(area); message('Request submitted.'); }
      catch (error) { message(error.message, true); } finally { submit.disabled = false; }
    };
  }
  async function updateProfileSchedule() {
    const label = [...document.querySelectorAll('.profile-meta-label')].find(el => el.textContent.trim() === 'Shift Schedule');
    const value = label?.parentElement.querySelector('.profile-meta-value'); if (!value) return;
    value.textContent = 'Loading schedule...';
    try {
      const rows = await getAll(`/api/shift-rosters/?start_date=${dateKey(new Date())}`);
      const next = rows.filter(r => r.work_date >= dateKey(new Date())).sort((a,b) => shiftLabel(a).localeCompare(shiftLabel(b)))[0];
      value.textContent = next ? `Next: ${shiftLabel(next)}` : 'No upcoming shift assigned.';
    } catch (_) { value.textContent = 'Schedule unavailable.'; }
  }
  async function showStaffArea(area, version) {
    const titles = {schedule:'My schedule', swaps:'Shift swaps', corrections:'Attendance corrections', overtime:'Overtime'};
    content.replaceChildren(node('h3', titles[area]), node('p', 'Loading...'));
    try {
      const today = new Date(); const end = new Date(today); end.setDate(end.getDate()+30);
      const [rosters, attendance, requests] = await Promise.all([
        area === 'schedule' ? getAll(`/api/shift-rosters/?start_date=${dateKey(today)}&end_date=${dateKey(end)}`) : area === 'swaps' ? getAll('/api/shift-rosters/') : [],
        ['corrections','overtime'].includes(area) ? getAll('/api/attendance/') : [],
        area === 'schedule' ? [] : getAll(`/api/${{swaps:'shift-swaps',corrections:'attendance-corrections',overtime:'overtime'}[area]}/`)
      ]);
      if (version !== renderVersion) return;
      content.replaceChildren(node('h3', titles[area]));
      if (area === 'schedule') {
        const filters = node('form', null, 'workflow-form workflow-date-filters');
        field(filters, 'From', 'start', 'date'); field(filters, 'To', 'end', 'date');
        filters.elements.start.value = dateKey(today); filters.elements.end.value = dateKey(end);
        const list = node('div', null, 'workflow-list');
        let first = true; let filterVersion = 0;
        const render = async () => {
          const stamp = ++filterVersion; list.textContent = 'Loading schedule...'; message('');
          try {
          if (filters.elements.start.value > filters.elements.end.value) throw new Error('The end date must be on or after the start date.');
          const source = first ? rosters : await getAll(`/api/shift-rosters/?start_date=${encodeURIComponent(filters.elements.start.value)}&end_date=${encodeURIComponent(filters.elements.end.value)}`); first = false;
          if (stamp !== filterVersion || version !== renderVersion) return; list.replaceChildren();
          const rows = source.filter(r => r.work_date >= filters.elements.start.value && r.work_date <= filters.elements.end.value).sort((a,b) => shiftLabel(a).localeCompare(shiftLabel(b)));
          if (!rows.length) list.append(node('p', 'No shifts in this period.'));
          rows.forEach(r => list.append(record('shift', r)));
          } catch (error) { if (stamp === filterVersion) { list.replaceChildren(); message(error.message, true); } }
        };
        filters.addEventListener('change', render); filters.onsubmit = e => e.preventDefault(); content.append(filters, list); render(); return;
      }
      const form = node('form', null, 'workflow-form');
      if (area === 'swaps') {
        const own = selectField(form, 'Your assigned shift', 'requester_roster', rosters.map(r => [r.id, shiftLabel(r)]));
        const dateWrap = node('label', 'Date of other shift'); const date = document.createElement('input'); date.type='date'; date.required=true; date.className='portal-input'; dateWrap.append(date); form.append(dateWrap);
        const other = selectField(form, 'Available shift', 'target_roster', []);
        const load = async () => {
          other.replaceChildren(new Option('Select...', '')); if (!date.value) return;
          other.disabled = true; message('');
          try { const rows = await getAll(`/api/shift-rosters/available-for-swap/?work_date=${encodeURIComponent(date.value)}`); rows.forEach(r => other.add(new Option(`${r.employee_name} · ${shiftLabel(r)}`, r.id))); if (!rows.length) message('No eligible shifts available on this date.'); }
          catch (error) { message(error.message, true); } finally { other.disabled = false; }
        };
        date.onchange = load; own.onchange = () => { if (own.value && !date.value) { date.value = rosters.find(r => String(r.id) === own.value)?.work_date || ''; load(); } };
        field(form, 'Reason', 'reason', 'textarea'); submitForm(form, '/api/shift-swaps/', data => Object.fromEntries(data), area);
      } else {
        selectField(form, 'Attendance record', 'attendance', attendance.map(a => [a.id, attendanceLabel(a)]));
        if (area === 'corrections') {
          field(form, 'Proposed clock in', 'proposed_clock_in', 'datetime-local'); field(form, 'Proposed clock out', 'proposed_clock_out', 'datetime-local');
          form.elements.proposed_clock_in.required = false; form.elements.proposed_clock_out.required = false;
          field(form, 'Reason', 'reason', 'textarea');
          submitForm(form, '/api/attendance-corrections/', data => {
            const values = Object.fromEntries(data); if (!values.proposed_clock_in && !values.proposed_clock_out) throw new Error('Enter at least one proposed time.');
            for (const key of ['proposed_clock_in','proposed_clock_out']) values[key] = values[key] ? new Date(values[key]).toISOString() : null;
            return values;
          }, area);
        } else {
          form.append(node('p', 'Hours and multiplier are calculated from the configured policy after submission.'));
          submitForm(form, '/api/overtime/', data => Object.fromEntries(data), area);
        }
      }
      content.append(form, node('h4', 'Request history'));
      const list = node('div', null, 'workflow-list'); content.append(list);
      if (!requests.length) list.append(node('p', 'No requests yet.'));
      const ownIds = new Set(rosters.map(r => String(r.id)));
      requests.forEach(item => {
        const display = area === 'swaps' ? {...item, requester_roster: item.requester_roster_display ? `${item.requester_employee_name || item.requester_roster_display.employee_name} · ${shiftLabel(item.requester_roster_display)}` : (rosters.find(r => String(r.id) === String(item.requester_roster)) ? shiftLabel(rosters.find(r => String(r.id) === String(item.requester_roster))) : item.requester_roster), target_roster: item.target_roster_display ? `${item.target_employee_name || item.target_roster_display.employee_name} · ${shiftLabel(item.target_roster_display)}` : (rosters.find(r => String(r.id) === String(item.target_roster)) ? shiftLabel(rosters.find(r => String(r.id) === String(item.target_roster))) : item.target_roster)} : item;
        const card = record({swaps:'swap',corrections:'correction',overtime:'overtime'}[area], display);
        if (area === 'swaps') {
          const employeeId = typeof myEmployeeId === 'undefined' ? '' : String(myEmployeeId);
          const incoming = item.target_employee ? String(item.target_employee) === employeeId : item.status === 'Pending' && ownIds.has(String(item.target_roster));
          const outgoing = item.requester_employee ? String(item.requester_employee) === employeeId : item.status === 'Pending' && ownIds.has(String(item.requester_roster));
          card.prepend(node('strong', incoming ? 'Incoming request' : outgoing ? 'Outgoing request' : 'Shift swap request'));
          if (incoming && item.status === 'Pending') {
            const buttons = node('div', null, 'workflow-actions');
            ['Approved','Rejected'].forEach(decision => buttons.append(action(decision === 'Approved' ? 'Approve' : 'Reject', async () => {
              buttons.querySelectorAll('button').forEach(b => b.disabled = true); message('');
              try { await request(`/api/shift-swaps/${encodeURIComponent(item.id)}/`, {method:'PATCH', body:JSON.stringify({status:decision})}); await showArea(area); message('Decision saved.'); }
              catch (error) { message(error.message, true); buttons.querySelectorAll('button').forEach(b => b.disabled = false); }
            }))); card.append(buttons);
          }
        }
        if (area === 'corrections') { const a = attendance.find(row => String(row.id) === String(item.attendance)); if (a) card.prepend(node('p', `Current: ${attendanceLabel(a)}`)); }
        list.append(card);
      });
    } catch (error) { if (version === renderVersion) { content.replaceChildren(node('h3', titles[area])); message(error.message, true); } }
  }
  updateProfileSchedule();

  button.addEventListener('click', () => { switchPortalTab('workflowsPanel'); showArea('notifications'); });
  panel.querySelectorAll('[data-area]').forEach(el => el.addEventListener('click', () => showArea(el.dataset.area)));
  document.getElementById('complaintRows').addEventListener('click', event => {
    const target = event.target.closest('[data-complaint-detail]');
    if (target) openDetail('complaint', target.dataset.complaintDetail);
  });
  window.addEventListener('notifications:changed', refreshNotifications);
  refreshNotifications();
  setInterval(() => { if (!document.hidden) refreshNotifications(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshNotifications(); });
})();
