// HR case registers and payroll entry use the server as the source of truth.
let hrCaseRegister = 'grievances';
let hrCases = { grievances: [], complaints: [] };
let payrollRuns = [];
let payrollLines = [];
let payrollEmployees = [];
let selectedPayrollId = null;

async function hrRequest(url, options = {}) {
  const response = await apiFetch(url, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = typeof data.detail === 'string' ? data.detail : typeof data.error === 'string' ? data.error : 'Please check the entered values and try again.';
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function selectHrCaseRegister(register) {
  hrCaseRegister = register;
  document.getElementById('hrGrievancesTab').classList.toggle('active', register === 'grievances');
  document.getElementById('hrComplaintsTab').classList.toggle('active', register === 'complaints');
  renderHrCases();
}

async function loadGrievanceView() {
  const list = document.getElementById('grievanceCaseList');
  if (!list) return;
  try {
    const [grievances, complaints, employees] = await Promise.all([
      fetchAllApiRows('/api/grievances/?page_size=100'), fetchAllApiRows('/api/complaints/?page_size=100'), fetchAllApiRows('/api/employees/?page_size=100')
    ]);
    hrCases = { grievances, complaints };
    const select = document.getElementById('grievComplainant');
    select.innerHTML = '<option value="">Select employee...</option>';
    employees.filter(e => e.is_active !== false).forEach(e => select.add(new Option(`${e.first_name || ''} ${e.last_name || ''}`.trim() || e.email, e.id)));
    document.getElementById('grievanceOpenCount').textContent = String(grievances.filter(g => !['Resolved', 'Rejected'].includes(g.status)).length).padStart(2, '0');
    document.getElementById('grievanceMediationCount').textContent = String(grievances.filter(g => g.status === 'In Mediation').length).padStart(2, '0');
    document.getElementById('grievanceResolvedCount').textContent = String(grievances.filter(g => g.status === 'Resolved').length).padStart(2, '0');
    renderHrCases();
  } catch (_) { list.textContent = 'Case registers could not be loaded.'; }
}

function renderHrCases() {
  const list = document.getElementById('grievanceCaseList');
  const items = hrCases[hrCaseRegister];
  list.innerHTML = '';
  if (!items.length) { list.textContent = `No ${hrCaseRegister} found.`; return; }
  items.forEach(item => {
    const isComplaint = hrCaseRegister === 'complaints';
    const terminalStates = isComplaint ? ['Resolved', 'Dismissed'] : ['Resolved', 'Rejected'];
    const terminal = terminalStates.includes(item.status);
    const transitions = isComplaint
      ? { 'Open': ['In Review'], 'In Review': ['Resolved', 'Dismissed'] }
      : { 'Pending': ['Investigating', 'Resolved', 'Rejected'], 'Investigating': ['In Mediation', 'Resolved', 'Rejected'], 'In Mediation': ['Resolved', 'Rejected'] };
    const states = [item.status, ...(transitions[item.status] || [])];
    const card = document.createElement('article');
    card.className = 'grievance-case-item hr-case';
    const reviewFields = terminal
      ? `<p><strong>Status:</strong> ${escapeHtml(item.status)}</p><p><strong>Resolution (visible to employee):</strong> ${escapeHtml(item.resolution || '')}</p>`
      : `<label>Status <select name="status">${states.map(s => `<option${s === item.status ? ' selected' : ''}>${escapeHtml(s)}</option>`).join('')}</select></label><label>Resolution (visible to employee)<textarea name="resolution" rows="2">${escapeHtml(item.resolution || '')}</textarea></label>`;
    card.innerHTML = `<h3>${escapeHtml(item.subject || item.title || '')}</h3><p class="case-submeta">${escapeHtml(item.employee_name || 'Anonymous Filing')} · ${escapeHtml(String(item.created_at || '').slice(0, 10))}</p><p>${escapeHtml(item.description || item.details || '')}</p><form>${reviewFields}<label>Internal notes (HR only)<textarea name="internal_notes" rows="2">${escapeHtml(item.internal_notes || '')}</textarea></label><button class="btn btn-navy-cta" type="submit">Save review</button></form>`;
    card.querySelector('form').addEventListener('submit', async event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const payload = {internal_notes: data.get('internal_notes')};
      if (!terminal) {
        payload.status = data.get('status');
        payload.resolution = data.get('resolution').trim();
        if (terminalStates.includes(payload.status) && !payload.resolution) { showToast('Enter a resolution for a closed case.', 'error'); return; }
      }
      try { await hrRequest(`/api/${isComplaint ? 'complaints' : 'grievances'}/${encodeURIComponent(item.id)}/`, { method: 'PATCH', body: JSON.stringify(payload) }); showToast('Case review saved.'); await loadGrievanceView(); }
      catch (_) { showToast('Case review could not be saved.', 'error'); }
    });
    if (isComplaint && !hrCases.grievances.some(g => String(g.source_complaint) === String(item.id))) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'tab-pill'; button.textContent = 'Escalate to grievance';
      button.onclick = async () => { if (!confirm('Create a grievance from this complaint?')) return; try { await hrRequest(`/api/complaints/${encodeURIComponent(item.id)}/escalate/`, {method: 'POST'}); showToast('Complaint escalated.'); await loadGrievanceView(); selectHrCaseRegister('grievances'); } catch (_) { showToast('Complaint could not be escalated.', 'error'); } };
      card.appendChild(button);
    }
    list.appendChild(card);
  });
}

async function handleGrievanceSubmit(event) {
  event.preventDefault();
  try {
    await hrRequest('/api/grievances/', { method: 'POST', body: JSON.stringify({employee: document.getElementById('grievComplainant').value, category: document.getElementById('grievCategory').value, title: document.getElementById('grievTitle').value.trim(), details: document.getElementById('grievDetails').value.trim()}) });
    event.target.reset(); showToast('Grievance filed.'); await loadGrievanceView(); selectHrCaseRegister('grievances');
  } catch (_) { showToast('Grievance could not be filed.', 'error'); }
}

async function loadPayrollView() {
  const container = document.getElementById('payrollRuns');
  if (!container) return;
  try {
    [payrollRuns, payrollEmployees] = await Promise.all([fetchAllApiRows('/api/payroll-runs/?page_size=100'), fetchAllApiRows('/api/employees/?page_size=100')]);
    container.innerHTML = '';
    if (!payrollRuns.length) container.textContent = 'No pay periods yet.';
    payrollRuns.forEach(run => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'hr-run-button';
      button.textContent = `${run.pay_period_start} – ${run.pay_period_end} · ${run.is_processed ? 'Processed' : 'Draft'}`;
      button.onclick = () => selectPayrollRun(run.id); container.appendChild(button);
    });
    if (selectedPayrollId && payrollRuns.some(r => r.id === selectedPayrollId)) await selectPayrollRun(selectedPayrollId);
  } catch (_) { container.textContent = 'Payroll data could not be loaded.'; }
}

async function createPayrollRun(event) {
  event.preventDefault();
  try { const run = await hrRequest('/api/payroll-runs/', {method: 'POST', body: JSON.stringify({pay_period_start: document.getElementById('payrollStart').value, pay_period_end: document.getElementById('payrollEnd').value})}); event.target.reset(); selectedPayrollId = run.id; await loadPayrollView(); showToast('Payroll draft created.'); }
  catch (error) { showToast(error.message, 'error'); }
}

async function selectPayrollRun(id) {
  selectedPayrollId = id;
  const run = payrollRuns.find(r => r.id === id);
  if (!run) return;
  const section = document.getElementById('payrollSelected'); section.hidden = false;
  document.getElementById('payrollSelectedTitle').textContent = `${run.pay_period_start} – ${run.pay_period_end} · ${run.is_processed ? 'Processed' : 'Draft'}`;
  document.getElementById('payrollItemForm').hidden = run.is_processed;
  document.getElementById('payrollFinalize').hidden = run.is_processed;
  const list = document.getElementById('payrollLines'); list.textContent = 'Loading lines...';
  try {
    payrollLines = await fetchAllApiRows(`/api/payroll-items/?payroll_run=${encodeURIComponent(id)}&page_size=100`);
    const select = document.getElementById('payrollEmployee'); select.innerHTML = '<option value="">Select employee...</option>';
    payrollEmployees.forEach(e => select.add(new Option(`${e.first_name || ''} ${e.last_name || ''}`.trim() || e.email, e.id)));
    resetPayrollItem(); list.innerHTML = '';
    if (!payrollLines.length) list.textContent = 'No payroll lines in this period.';
    payrollLines.forEach(line => {
      const employee = payrollEmployees.find(e => e.id === line.employee);
      const row = document.createElement('div'); row.className = 'hr-payroll-line';
      row.innerHTML = `<strong>${escapeHtml(employee ? `${employee.first_name} ${employee.last_name}` : String(line.employee))}</strong><span>Base: ${escapeHtml(String(line.base_pay))}</span><span>Deductions: ${escapeHtml(String(line.deductions))}</span><span>Net: ${escapeHtml(String(line.net_pay))}</span>`;
      if (!run.is_processed) {
        const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'tab-pill'; edit.textContent = 'Edit'; edit.onclick = () => editPayrollItem(line.id); row.appendChild(edit);
        const del = document.createElement('button'); del.type = 'button'; del.className = 'tab-pill'; del.textContent = 'Delete'; del.onclick = () => deletePayrollItem(line.id); row.appendChild(del);
      }
      list.appendChild(row);
    });
  } catch (_) { list.textContent = 'Payroll lines could not be loaded.'; }
}

function resetPayrollItem() { document.getElementById('payrollItemForm').reset(); document.getElementById('payrollItemId').value = ''; document.getElementById('payrollEmployee').disabled = false; document.getElementById('payrollSave').textContent = 'Add line'; previewPayrollNet(); }
function editPayrollItem(id) { const line = payrollLines.find(i => i.id === id); if (!line) return; document.getElementById('payrollItemId').value = id; document.getElementById('payrollEmployee').value = line.employee; document.getElementById('payrollEmployee').disabled = true; document.getElementById('payrollBase').value = line.base_pay; document.getElementById('payrollDeductions').value = line.deductions; document.getElementById('payrollSave').textContent = 'Save line'; previewPayrollNet(); document.getElementById('payrollBase').focus(); }
function previewPayrollNet() {
  const base = document.getElementById('payrollBase').value, deductions = document.getElementById('payrollDeductions').value;
  const cents = value => { const parts = value.split('.'); return BigInt(parts[0] || '0') * 100n + BigInt((parts[1] || '').padEnd(2, '0')); };
  let text = 'Estimated net: —';
  if (/^\d+(\.\d{1,2})?$/.test(base) && /^\d+(\.\d{1,2})?$/.test(deductions)) {
    const net = cents(base) - cents(deductions), absolute = net < 0n ? -net : net;
    text = `Estimated net: ${net < 0n ? '-' : ''}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')} (confirmed by server on save)`;
  }
  document.getElementById('payrollPreview').textContent = text;
}
async function savePayrollItem(event) {
  event.preventDefault(); const id = document.getElementById('payrollItemId').value;
  const data = {base_pay: document.getElementById('payrollBase').value, deductions: document.getElementById('payrollDeductions').value};
  if (!id) { data.payroll_run = selectedPayrollId; data.employee = document.getElementById('payrollEmployee').value; }
  try { await hrRequest(id ? `/api/payroll-items/${encodeURIComponent(id)}/` : '/api/payroll-items/', {method: id ? 'PATCH' : 'POST', body: JSON.stringify(data)}); await selectPayrollRun(selectedPayrollId); showToast('Payroll line saved.'); } catch (error) { showToast(error.message, 'error'); }
}
async function deletePayrollItem(id) { if (!confirm('Delete this draft payroll line?')) return; try { await hrRequest(`/api/payroll-items/${encodeURIComponent(id)}/`, {method: 'DELETE'}); await selectPayrollRun(selectedPayrollId); showToast('Payroll line deleted.'); } catch (error) { showToast(error.message, 'error'); } }
async function finalizePayroll() { if (!confirm('Finalize this payroll period? Its lines can no longer be edited or deleted.')) return; try { await hrRequest(`/api/payroll-runs/${encodeURIComponent(selectedPayrollId)}/finalize/`, {method: 'POST'}); await loadPayrollView(); showToast('Payroll finalized.'); } catch (error) { showToast(error.message, 'error'); } }

function openNotifInbox(event) { if (event) event.preventDefault(); switchView('notifications'); loadHrNotifications(); }
async function loadHrNotifications() {
  const list = document.getElementById('hrNotifications');
  list.textContent = 'Loading notifications...';
  try {
    const notes = await fetchAllApiRows('/api/notifications/?page_size=100'); list.innerHTML = '';
    if (!notes.length) { list.textContent = 'No notifications.'; return; }
    notes.forEach(note => {
      const row = document.createElement('article'); row.className = 'hr-payroll-line';
      const text = document.createElement('span'); text.textContent = `${note.is_read ? 'Read' : 'Unread'} · ${note.text || ''}`; row.appendChild(text);
      if (!note.is_read) { const button = document.createElement('button'); button.type = 'button'; button.className = 'tab-pill'; button.textContent = 'Mark read'; button.onclick = async () => { try { await hrRequest(`/api/notifications/${encodeURIComponent(note.id)}/read/`, {method: 'PATCH'}); await loadHrNotifications(); refreshNotifBell(); } catch (_) { showToast('Notification could not be marked read.', 'error'); } }; row.appendChild(button); }
      list.appendChild(row);
    });
  } catch (_) { list.textContent = 'Notifications could not be loaded.'; }
}
