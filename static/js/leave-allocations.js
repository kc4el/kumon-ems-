/* Leave entitlement administration and employee balance display. */
(() => {
  const hrView = document.getElementById('view-attendance-leave');
  const host = hrView || document.getElementById('leavePanel');
  if (!host) return;
  const isHr = Boolean(hrView);
  const portalEmployee = isHr ? null : document.getElementById('leaveEmployee');
  const section = document.createElement('section');
  section.className = isHr ? 'white-card leave-allocation-card' : 'portal-card leave-allocation-card';
  const el = (tag, text) => { const node = document.createElement(tag); if (text != null) node.textContent = text; return node; };
  const heading = el('h2', isHr ? 'Annual leave allocations' : 'My leave balances');
  heading.className = isHr ? 'card-title' : 'portal-card-title'; section.append(heading);
  section.append(el('p', 'Approved leave is counted in calendar days. An allocation overrides the default entitlement for its leave type and year.'));
  const controls = el('div'); controls.className = 'leave-allocation-controls';
  const yearLabel = el('label', 'Year '); const year = el('input');
  year.type = 'number'; year.min = '1'; year.max = '9999'; year.required = true;
  year.value = String(new Date().getFullYear()); yearLabel.append(year); controls.append(yearLabel);
  const refresh = el('button', 'Refresh'); refresh.type = 'button'; refresh.className = 'tab-pill'; controls.append(refresh); section.append(controls);
  const status = el('p'); status.setAttribute('role', 'status'); section.append(status);
  const balances = el('div'); balances.setAttribute('aria-live', 'polite');
  const allocationList = el('div'); allocationList.className = 'leave-allocation-list';
  let rows = [], employees = [], editing = null, requestVersion = 0;
  let form, employee, type, days, save, cancel;

  function field(label, input, parent = form) {
    const wrap = el('label', label); wrap.append(input); parent.append(wrap); return input;
  }
  function button(label, callback) {
    const b = el('button', label); b.type = 'button'; b.className = 'tab-pill';
    b.onclick = callback; return b;
  }
  async function request(url, options = {}) {
    const response = await (isHr ? apiFetch(url, options) : portalFetch(url, options));
    if (response.status === 204) return null;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : typeof data.error === 'string' ? data.error : Object.entries(data).map(([k,v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`).join(' ') || 'The request could not be completed.');
    return data;
  }
  async function all(url) {
    const rows = [];
    while (url) {
      const parsed = new URL(url, location.origin);
      if (parsed.origin !== location.origin || !parsed.pathname.startsWith('/api/')) throw new Error('Invalid page link.');
      const data = await request(parsed.pathname + parsed.search);
      rows.push(...(Array.isArray(data) ? data : data.results || []));
      url = Array.isArray(data) ? null : data.next;
    }
    return rows;
  }
  function resetEdit() {
    editing = null; if (!isHr) return;
    employee.disabled = type.disabled = year.disabled = false;
    type.value = ''; days.value = ''; save.textContent = 'Add allocation'; cancel.hidden = true;
  }
  function table(headers) {
    const wrap = el('div'); wrap.className = 'leave-allocation-table-wrap';
    const t = el('table'); t.className = 'claims-table';
    const head = el('thead'), row = el('tr');
    headers.forEach(label => { const th = el('th', label); th.scope = 'col'; row.append(th); });
    head.append(row); const body = el('tbody'); t.append(head, body); wrap.append(t); return {wrap, body};
  }
  function renderRows() {
    allocationList.replaceChildren();
    const shown = rows.filter(r => !employee.value || String(r.employee) === employee.value);
    if (!shown.length) { allocationList.append(el('p', 'No explicit allocations for this selection. Default entitlements may still apply.')); return; }
    const {wrap, body} = table(['Employee', 'Leave type', 'Year', 'Allocated days', 'Actions']);
    shown.forEach(row => {
      const tr = el('tr'); const person = employees.find(e => String(e.id) === String(row.employee));
      [person ? `${person.first_name} ${person.last_name}` : row.employee, row.leave_type, row.year, row.days_total].forEach(value => tr.append(el('td', String(value))));
      const actions = el('td');
      actions.append(button('Edit', () => {
        editing = row.id; employee.value = String(row.employee); type.value = row.leave_type; days.value = row.days_total;
        employee.disabled = type.disabled = year.disabled = true;
        save.textContent = 'Save allocation'; cancel.hidden = false; days.focus(); loadBalances();
      }));
      actions.append(button('Remove override', async () => {
        if (!confirm('Remove this allocation override? Default entitlement will apply where configured. Use zero days to explicitly set no entitlement.')) return;
        actions.querySelectorAll('button').forEach(b => b.disabled = true);
        try { await request(`/api/leave-allocations/${encodeURIComponent(row.id)}/`, {method:'DELETE'}); resetEdit(); if (await load()) status.textContent = 'Allocation override removed.'; }
        catch (error) { status.textContent = error.message; actions.querySelectorAll('button').forEach(b => b.disabled = false); }
      }));
      tr.append(actions); body.append(tr);
    }); allocationList.append(wrap);
  }
  async function loadBalances(stamp = requestVersion) {
    balances.replaceChildren();
    if (isHr && !employee.value) { balances.append(el('p', 'Select an employee to review their balances.')); return true; }
    if (portalEmployee && !portalEmployee.value) { balances.append(el('p', 'Choose an employee in the leave request form to review their balances.')); return true; }
    const params = new URLSearchParams({year:year.value});
    if (isHr) params.set('employee', employee.value);
    if (portalEmployee) params.set('employee', portalEmployee.value);
    const selected = isHr ? employee.value : portalEmployee?.value || '';
    try {
      const data = await request('/api/leave-balances/?' + params);
      if (stamp !== requestVersion || selected !== (isHr ? employee.value : portalEmployee?.value || '')) return;
      const {wrap, body} = table(['Leave type', 'Allocated days', 'Used days', 'Remaining days']);
      Object.entries(data.balances || {}).forEach(([name, value]) => {
        const tr = el('tr'); [name, value.allocated, value.used, value.remaining].forEach(v => tr.append(el('td', String(v)))); body.append(tr);
      });
      balances.replaceChildren(el('h3', `Leave balances for ${data.year}`), wrap);
      return true;
    } catch (error) { if (stamp === requestVersion) status.textContent = error.message; return false; }
  }
  async function load() {
    if (!year.reportValidity()) return;
    const stamp = ++requestVersion; status.textContent = 'Loading leave information...';
    try {
      if (isHr) {
        const [allocations, people] = await Promise.all([all('/api/leave-allocations/?year=' + encodeURIComponent(year.value)), all('/api/employees/')]);
        if (stamp !== requestVersion) return;
        rows = allocations; employees = people;
        const selected = employee.value;
        employee.replaceChildren(new Option('Select employee...', ''));
        employees.forEach(p => employee.add(new Option(`${p.first_name} ${p.last_name}${p.is_active === false ? ' (inactive)' : ''}`, p.id)));
        employee.value = selected; renderRows();
      }
      if (stamp !== requestVersion) return;
      status.textContent = ''; return await loadBalances(stamp);
    } catch (error) { if (stamp === requestVersion) { allocationList.replaceChildren(); balances.replaceChildren(); status.textContent = error.message; } return false; }
  }
  if (isHr) {
    form = el('form'); form.className = 'leave-allocation-form';
    employee = field('Employee', el('select')); employee.required = true;
    type = field('Leave type', el('input')); type.required = true; type.maxLength = 50; type.placeholder = 'Vacation';
    days = field('Allocated days', el('input')); days.type = 'number'; days.min = '0'; days.max = '999.9'; days.step = '0.1'; days.required = true;
    save = el('button', 'Add allocation'); save.type = 'submit'; save.className = 'tab-pill';
    cancel = button('Cancel edit', resetEdit); cancel.hidden = true; form.append(save, cancel); section.append(form);
    employee.onchange = () => { ++requestVersion; renderRows(); loadBalances(); };
    form.onsubmit = async event => {
      event.preventDefault(); if (!form.reportValidity() || !year.reportValidity()) return;
      const data = editing ? {days_total:days.value} : {employee:employee.value, leave_type:type.value.trim(), year:Number(year.value), days_total:days.value};
      save.disabled = true; status.textContent = '';
      try {
        await request(editing ? `/api/leave-allocations/${encodeURIComponent(editing)}/` : '/api/leave-allocations/', {method:editing ? 'PATCH' : 'POST', body:JSON.stringify(data)});
        resetEdit(); if (await load()) status.textContent = 'Allocation saved.';
      } catch (error) { status.textContent = error.message; } finally { save.disabled = false; }
    };
  }
  section.append(balances); if (isHr) section.append(allocationList);
  host.prepend(section);
  year.onchange = () => { resetEdit(); load(); };
  if (portalEmployee) portalEmployee.addEventListener('change', () => { ++requestVersion; loadBalances(); });
  refresh.onclick = () => load();
  const observer = new MutationObserver(() => { if (host.classList.contains('active')) load(); });
  observer.observe(host, {attributes:true, attributeFilter:['class']});
  window.addEventListener('notifications:changed', () => { if (!document.hidden && host.classList.contains('active')) load(); });
  setInterval(() => { if (!document.hidden && host.classList.contains('active') && !editing) load(); }, 30000);
  if (host.classList.contains('active')) load();
})();
