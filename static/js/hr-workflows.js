// HR case registers and pay estimates use the server as the source of truth.
let hrCaseRegister = 'grievances';
let hrCases = { grievances: [], complaints: [] };
// Drafts survive register switches and background refreshes until their own save succeeds.
const hrCaseDrafts = new Map();
const hrCaseSaves = new Set();
let hrCaseLoadVersion = 0;
function hrCaseKey(register, id) { return `${register}:${id}`; }
function hrCaseValues(form, terminal) {
  return {
    internal_notes: form.elements.internal_notes.value,
    ...(!terminal ? { status: form.elements.status.value, resolution: form.elements.resolution.value } : {})
  };
}
function hrCaseServerValues(item, terminal) {
  return { internal_notes: item.internal_notes || '', ...(!terminal ? { status: item.status, resolution: item.resolution || '' } : {}) };
}
function hrSameCaseValues(a, b) { return JSON.stringify(a) === JSON.stringify(b); }


async function hrRequest(url, options = {}) {
  const response = await apiFetch(url, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = typeof data.detail === 'string' ? data.detail : typeof data.error === 'string' ? data.error : Object.entries(data).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${Array.isArray(value) ? value.join(' ') : value}`).join(' ') || 'Please check the entered values and try again.';
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
  const loadVersion = ++hrCaseLoadVersion;
  try {
    const [grievances, complaints, employees] = await Promise.all([
      fetchAllApiRows('/api/grievances/?page_size=100'), fetchAllApiRows('/api/complaints/?page_size=100'), fetchAllApiRows('/api/employees/?page_size=100')
    ]);
    if (loadVersion !== hrCaseLoadVersion) return;
    hrCases = { grievances, complaints };
    const select = document.getElementById('grievComplainant');
    const previousEmployee = select.value;
    select.innerHTML = '<option value="">Select employee...</option>';
    employees.filter(e => e.is_active !== false).forEach(e => select.add(new Option(`${e.first_name || ''} ${e.last_name || ''}`.trim() || e.email, e.id)));
    select.value = previousEmployee;
    document.getElementById('grievanceOpenCount').textContent = String(grievances.filter(g => !['Resolved', 'Rejected'].includes(g.status)).length).padStart(2, '0');
    document.getElementById('grievanceMediationCount').textContent = String(grievances.filter(g => g.status === 'In Mediation').length).padStart(2, '0');
    document.getElementById('grievanceResolvedCount').textContent = String(grievances.filter(g => g.status === 'Resolved').length).padStart(2, '0');
    renderHrCases();
  } catch (_) { if (loadVersion === hrCaseLoadVersion && !hrCaseDrafts.size) list.textContent = 'Case registers could not be loaded.'; }
}

function renderHrCases() {
  const list = document.getElementById('grievanceCaseList');
  const items = hrCases[hrCaseRegister];
  const active = document.activeElement;
  const activeCard = active && active.closest && active.closest('[data-case-key]');
  const focus = activeCard && list.contains(activeCard) ? {
    key: activeCard.dataset.caseKey, name: active.name,
    start: active.selectionStart, end: active.selectionEnd
  } : null;
  list.innerHTML = '';
  if (!items.length) { list.textContent = `No ${hrCaseRegister} found.`; return; }
  items.forEach(item => {
    const isComplaint = hrCaseRegister === 'complaints';
    const terminalStates = isComplaint ? ['Resolved', 'Dismissed'] : ['Resolved', 'Rejected'];
    const key = hrCaseKey(hrCaseRegister, item.id);
    const draft = hrCaseDrafts.get(key);
    // A draft started before the server closed a case must remain editable.
    const terminal = draft ? draft.terminal : terminalStates.includes(item.status);
    const transitions = isComplaint
      ? { 'Open': ['In Review'], 'In Review': ['Resolved', 'Dismissed'] }
      : { 'Pending': ['Investigating', 'Resolved', 'Rejected'], 'Investigating': ['In Mediation', 'Resolved', 'Rejected'], 'In Mediation': ['Resolved', 'Rejected'] };
    const states = [...new Set([item.status, ...(transitions[item.status] || []), ...(draft && draft.values.status ? [draft.values.status] : [])])];
    const card = document.createElement('article');
    card.className = 'grievance-case-item hr-case';
    card.dataset.caseKey = key;
    const reviewFields = terminal
      ? `<p><strong>Status:</strong> ${escapeHtml(item.status)}</p><p><strong>Resolution (visible to employee):</strong> ${escapeHtml(item.resolution || '')}</p>`
      : `<label>Status <select name="status">${states.map(s => `<option${s === item.status ? ' selected' : ''}>${escapeHtml(s)}</option>`).join('')}</select></label><label>Resolution (visible to employee)<textarea name="resolution" rows="2">${escapeHtml(item.resolution || '')}</textarea></label>`;
    card.innerHTML = `<h3>${escapeHtml(item.subject || item.title || '')}</h3><p class="case-submeta">${escapeHtml(item.employee_name || 'Anonymous Filing')} · ${escapeHtml(String(item.created_at || '').slice(0, 10))}</p><p>${escapeHtml(item.description || item.details || '')}</p><form>${reviewFields}<label>Internal notes (HR only)<textarea name="internal_notes" rows="2">${escapeHtml(item.internal_notes || '')}</textarea></label><button class="btn btn-navy-cta" type="submit">Save review</button></form>`;
    const form = card.querySelector('form');
    if (draft) {
      form.elements.internal_notes.value = draft.values.internal_notes;
      if (!terminal) {
        form.elements.status.value = draft.values.status;
        form.elements.resolution.value = draft.values.resolution;
      }
      if (!hrSameCaseValues(draft.baseline, hrCaseServerValues(item, terminal))) {
        const notice = document.createElement('p');
        notice.textContent = 'This case has changed on the server. Your unsaved review is preserved; check it before saving.';
        card.insertBefore(notice, form);
      }
    }
    const baseline = draft ? draft.baseline : hrCaseServerValues(item, terminal);
    const rememberDraft = () => {
      const values = hrCaseValues(form, terminal);
      if (!hrCaseSaves.has(key) && hrSameCaseValues(values, baseline)) hrCaseDrafts.delete(key);
      else hrCaseDrafts.set(key, { values, baseline, terminal });
    };
    form.addEventListener('input', rememberDraft);
    form.addEventListener('change', rememberDraft);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const payload = {internal_notes: data.get('internal_notes')};
      if (!terminal) {
        payload.status = data.get('status');
        payload.resolution = data.get('resolution').trim();
        if (terminalStates.includes(payload.status) && !payload.resolution) { showToast('Enter a resolution for a closed case.', 'error'); return; }
      }
      if (hrCaseSaves.has(key)) return;
      const submittedValues = hrCaseValues(form, terminal);
      hrCaseSaves.add(key);
      hrCaseDrafts.set(key, { values: submittedValues, baseline, terminal });
      try {
        await hrRequest(`/api/${isComplaint ? 'complaints' : 'grievances'}/${encodeURIComponent(item.id)}/`, { method: 'PATCH', body: JSON.stringify(payload) });
        // Invalidate reads started before the write, and keep edits made while saving.
        ++hrCaseLoadVersion;
        const current = hrCaseDrafts.get(key);
        if (current && hrSameCaseValues(current.values, submittedValues)) hrCaseDrafts.delete(key);
        else if (current) current.baseline = submittedValues;
        hrCaseSaves.delete(key);
        showToast('Case review saved.');
        await loadGrievanceView();
      }
      catch (_) { hrCaseSaves.delete(key); showToast('Case review could not be saved.', 'error'); }
    });
    if (isComplaint && !hrCases.grievances.some(g => String(g.source_complaint) === String(item.id))) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'tab-pill'; button.textContent = 'Escalate to grievance';
      button.onclick = async () => { if (!confirm('Create a grievance from this complaint?')) return; try { await hrRequest(`/api/complaints/${encodeURIComponent(item.id)}/escalate/`, {method: 'POST'}); showToast('Complaint escalated.'); await loadGrievanceView(); selectHrCaseRegister('grievances'); } catch (_) { showToast('Complaint could not be escalated.', 'error'); } };
      card.appendChild(button);
    }
    list.appendChild(card);
    if (focus && focus.key === key && form.elements[focus.name]) {
      const field = form.elements[focus.name];
      field.focus();
      if (typeof focus.start === 'number' && field.setSelectionRange) field.setSelectionRange(focus.start, focus.end);
    }
  });
}

async function handleGrievanceSubmit(event) {
  event.preventDefault();
  try {
    await hrRequest('/api/grievances/', { method: 'POST', body: JSON.stringify({employee: document.getElementById('grievComplainant').value, category: document.getElementById('grievCategory').value, title: document.getElementById('grievTitle').value.trim(), details: document.getElementById('grievDetails').value.trim()}) });
    event.target.reset(); showToast('Grievance filed.'); await loadGrievanceView(); selectHrCaseRegister('grievances');
  } catch (_) { showToast('Grievance could not be filed.', 'error'); }
}

let estimateRecords = [];
let selectedEstimate = null;
let editingEstimateId = null;

async function estimateAction(button, action) {
  if (button.disabled) return;
  button.disabled = true;
  try { await action(); } catch (error) { showToast(error.message || 'The request could not be completed.', 'error'); }
  finally { button.disabled = false; }
}

async function loadPayEstimates() {
  const list = document.getElementById('estimateList');
  if (!list) return;
  try {
    const [estimates, employees, policies] = await Promise.all([
      fetchAllApiRows('/api/pay-estimates/'), fetchAllApiRows('/api/employees/?page_size=100'), fetchAllApiRows('/api/pay-estimate-policies/')
    ]);
    estimateRecords = estimates;
    const select = document.getElementById('estimateEmployee');
    const previous = select.value;
    select.replaceChildren(new Option('Select employee...', ''));
    employees.forEach(e => select.add(new Option(`${e.first_name || ''} ${e.last_name || ''}`.trim() || e.email || String(e.id), e.id)));
    select.value = previous;
    const policyList = document.getElementById('estimatePolicies');
    policyList.textContent = policies.length ? policies.map(p => `From ${p.effective_date}: overtime ${p.overtime_threshold_hours == null || p.overtime_multiplier == null ? 'not assessed' : `after ${p.overtime_threshold_hours} hours at ${p.overtime_multiplier}x`}; paid leave: ${(p.paid_leave_types || []).join(', ') || 'none designated'}`).join(' | ') : 'No rules configured yet.';
    list.replaceChildren();
    if (!estimates.length) list.textContent = 'No estimates yet.';
    estimates.forEach(item => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'hr-run-button';
      button.textContent = `${item.employee_name || item.employee} · ${item.period_start} to ${item.period_end}`;
      button.onclick = () => selectPayEstimate(item.id);
      list.appendChild(button);
    });
    if (selectedEstimate && estimates.some(e => String(e.id) === String(selectedEstimate.id))) await selectPayEstimate(selectedEstimate.id);
  } catch (error) { list.textContent = 'Estimates could not be loaded.'; showToast(error.message, 'error'); }
}

async function saveEstimatePolicy(event) {
  event.preventDefault(); const form = event.currentTarget;
  const threshold = document.getElementById('policyThreshold').value;
  const multiplier = document.getElementById('policyMultiplier').value;
  if (!!threshold !== !!multiplier) { showToast('Enter both overtime fields, or leave both blank.', 'error'); return; }
  await estimateAction(form.querySelector('button[type="submit"], button:not([type])'), async () => {
    await hrRequest('/api/pay-estimate-policies/', {method: 'POST', body: JSON.stringify({effective_date: document.getElementById('policyDate').value, overtime_threshold_hours: threshold || null, overtime_multiplier: multiplier || null, paid_leave_types: document.getElementById('policyLeaveTypes').value.split(',').map(x => x.trim()).filter(Boolean)})});
    form.reset(); showToast('Estimate rules saved.'); await loadPayEstimates();
  });
}

function resetEstimateForm() {
  editingEstimateId = null; document.getElementById('estimateForm').reset();
  document.getElementById('estimateFormTitle').textContent = 'Create estimate';
  document.getElementById('estimateSave').textContent = 'Create estimate';
  document.getElementById('estimateCancel').hidden = true;
}
function editPayEstimate() {
  if (!selectedEstimate) return;
  editingEstimateId = selectedEstimate.id;
  ['Employee', 'Start', 'End', 'Rate', 'Deductions'].forEach((field, i) => { document.getElementById(`estimate${field}`).value = selectedEstimate[['employee', 'period_start', 'period_end', 'hourly_rate', 'deductions'][i]]; });
  document.getElementById('estimateFormTitle').textContent = 'Edit estimate'; document.getElementById('estimateSave').textContent = 'Save changes'; document.getElementById('estimateCancel').hidden = false;
  document.getElementById('estimateEmployee').focus();
}
async function savePayEstimate(event) {
  event.preventDefault(); const form = event.currentTarget;
  const payload = {employee: document.getElementById('estimateEmployee').value, period_start: document.getElementById('estimateStart').value, period_end: document.getElementById('estimateEnd').value, hourly_rate: document.getElementById('estimateRate').value, deductions: document.getElementById('estimateDeductions').value};
  await estimateAction(document.getElementById('estimateSave'), async () => {
    const result = await hrRequest(editingEstimateId ? `/api/pay-estimates/${encodeURIComponent(editingEstimateId)}/` : '/api/pay-estimates/', {method: editingEstimateId ? 'PATCH' : 'POST', body: JSON.stringify(payload)});
    const wasEditing = !!editingEstimateId; selectedEstimate = result; resetEstimateForm(); await loadPayEstimates(); showToast(wasEditing ? 'Inputs saved. Recalculate to review current sources.' : 'Estimate created. Review its sources and adjustments.');
  });
}

async function selectPayEstimate(id, revisionNumber) {
  const detail = document.getElementById('estimateDetail'); detail.hidden = false; detail.textContent = 'Loading estimate...';
  try {
    const historical = revisionNumber != null;
    const data = await hrRequest(`/api/pay-estimates/${encodeURIComponent(id)}/${historical ? `revisions/${encodeURIComponent(revisionNumber)}/` : ''}`);
    if (!historical) selectedEstimate = data;
    renderPayEstimate(data, historical);
  } catch (error) { detail.textContent = 'Estimate could not be loaded.'; showToast(error.message, 'error'); }
}

function renderPayEstimate(data, historical) {
  const detail = document.getElementById('estimateDetail'); const rev = data.revision;
  const esc = value => escapeHtml(String(value == null ? '' : value));
  const hours = seconds => (Number(seconds || 0) / 3600).toFixed(2);
  detail.replaceChildren();
  const snapshot = rev?.input_snapshot || {};
  const title = document.createElement('h2'); title.className = 'card-title'; title.textContent = `${data.employee_name || data.employee} · ${snapshot.period_start || data.period_start} to ${snapshot.period_end || data.period_end}`; detail.appendChild(title);
  const intro = document.createElement('p'); intro.textContent = 'Pay estimate — pay-handler reference. Amounts are advisory.'; detail.appendChild(intro);
  const controls = document.createElement('div'); controls.className = 'estimate-controls'; detail.appendChild(controls);
  const button = (label, action) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'tab-pill'; b.textContent = label; b.onclick = () => action(b); controls.appendChild(b); return b; };
  if (historical) button('Back to current estimate', () => selectPayEstimate(data.id));
  else {
    button('Edit inputs', editPayEstimate);
    button('Recalculate', b => estimateAction(b, async () => { await hrRequest(`/api/pay-estimates/${encodeURIComponent(data.id)}/recalculate/`, {method: 'POST'}); await selectPayEstimate(data.id); showToast('Estimate recalculated.'); }));
    button('Export reference (CSV)', b => estimateAction(b, async () => {
      const response = await apiFetch(`/api/pay-estimates/${encodeURIComponent(data.id)}/export/?format=csv`);
      if (!response.ok) throw new Error('Export could not be prepared.');
      const url = URL.createObjectURL(await response.blob()); const a = document.createElement('a'); a.href = url; a.download = `pay-estimate-${data.id}.csv`; a.click(); URL.revokeObjectURL(url);
    }));
  }
  if (data.current_revision > 1) {
    const label = document.createElement('label'); label.textContent = 'View revision ';
    const select = document.createElement('select'); select.setAttribute('aria-label', 'View revision');
    for (let n = 1; n <= data.current_revision; n++) select.add(new Option(`Revision ${n}${n === data.current_revision ? ' (current)' : ''}`, String(n)));
    select.value = String(rev?.number || data.current_revision);
    select.onchange = () => Number(select.value) === data.current_revision ? selectPayEstimate(data.id) : selectPayEstimate(data.id, select.value);
    label.appendChild(select); controls.appendChild(label);
  }
  if (!rev) { const p = document.createElement('p'); p.textContent = 'No calculation yet. Recalculate to review this estimate.'; detail.appendChild(p); return; }
  const status = document.createElement('p'); status.className = rev.is_stale ? 'estimate-warning' : 'estimate-status';
  status.textContent = historical ? `Revision ${rev.number} · Historical, read only` : rev.is_stale ? 'This estimate is out of date. Recalculate before approving adjustments or using its total.' : rev.is_complete ? `Revision ${rev.number} · Current` : `Revision ${rev.number} · Incomplete; review warnings`;
  detail.appendChild(status);
  const summary = document.createElement('div'); summary.className = 'estimate-summary';
  summary.innerHTML = `<span>Hourly rate <strong>${esc(snapshot.hourly_rate ?? data.hourly_rate)}</strong></span><span>Base amount <strong>${esc(rev.base_amount)}</strong></span><span>Deductions <strong>${esc(rev.deductions)}</strong></span><span>Approved adjustments <strong>${esc(rev.approved_adjustments)}</strong></span><span>Pending adjustments <strong>${esc(rev.pending_adjustments)}</strong></span><span>Estimated amount <strong>${esc((historical ? rev.snapshot_estimate : rev.approved_estimate) ?? 'Unavailable')}</strong></span>`; detail.appendChild(summary);
  if ((rev.warnings || []).length) { const warnings = document.createElement('div'); warnings.className = 'estimate-warning'; const h = document.createElement('strong'); h.textContent = 'Review these items'; warnings.appendChild(h); const ul = document.createElement('ul'); rev.warnings.forEach(w => { const li = document.createElement('li'); li.textContent = typeof w === 'string' ? w : JSON.stringify(w); ul.appendChild(li); }); warnings.appendChild(ul); detail.appendChild(warnings); }
  const lines = document.createElement('div'); lines.innerHTML = '<h3>Attendance breakdown</h3>'; detail.appendChild(lines);
  if (!(rev.lines || []).length) lines.append('No attendance lines.');
  (rev.lines || []).forEach(line => { const row = document.createElement('div'); row.className = 'estimate-line'; row.textContent = `${line.work_date || 'Attendance'} · Worked ${hours(line.worked_seconds)} h · Break ${hours(line.break_seconds)} h · Net ${hours(line.paid_seconds)} h · Base ${line.base_amount}`; lines.appendChild(row); });
  const rounding = document.createElement('p'); rounding.textContent = `Rounding reconciliation: ${rev.rounding_reconciliation ?? 'Unavailable'} (daily amounts are rounded separately from the period base).`; lines.appendChild(rounding);
  const adjustments = document.createElement('div'); adjustments.innerHTML = '<h3>Adjustments</h3>'; detail.appendChild(adjustments);
  if (!(rev.adjustments || []).length) adjustments.append('No adjustments.');
  (rev.adjustments || []).forEach(adj => {
    const row = document.createElement('div'); row.className = 'estimate-adjustment';
    const calculation = String(adj.kind).toLowerCase().includes('overtime') ? `${adj.hours} h × ${adj.hourly_rate} × (${adj.multiplier} − 1) premium` : `${adj.hours} h × ${adj.hourly_rate}`;
    const description = document.createElement('p'); description.textContent = `${adj.kind} · ${adj.work_date || ''} · ${calculation} = ${adj.amount} · ${adj.status}${adj.reason ? ` · ${adj.reason}` : ''}`; row.appendChild(description);
    if (!historical && !rev.is_stale && adj.status === 'Pending') {
      const input = document.createElement('input'); input.placeholder = 'Reason for decision'; input.setAttribute('aria-label', 'Reason for adjustment decision'); row.appendChild(input);
      ['Approved', 'Rejected'].forEach(decision => { const b = document.createElement('button'); b.type = 'button'; b.className = 'tab-pill'; b.textContent = decision === 'Approved' ? 'Approve' : 'Reject'; if (decision === 'Approved' && !rev.is_complete) { b.disabled = true; b.title = 'Resolve incomplete sources before approval.'; } b.onclick = () => estimateAction(b, async () => {
        if (!input.value.trim()) throw new Error('Enter a reason for this decision.');
        row.querySelectorAll('button').forEach(x => { x.disabled = true; });
        try { await hrRequest(`/api/pay-estimate-adjustments/${encodeURIComponent(adj.id)}/decision/`, {method: 'POST', body: JSON.stringify({status: decision, reason: input.value.trim()})}); await selectPayEstimate(data.id); showToast('Adjustment decision saved.'); }
        catch (error) { row.querySelectorAll('button').forEach(x => { x.disabled = x.textContent === 'Approve' && !rev.is_complete; }); throw error; }
      }); row.appendChild(b); });
    }
    adjustments.appendChild(row);
  });
}

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
      const reviewTypes = {shift_swap:'swaps', swap:'swaps', attendance_correction:'corrections', correction:'corrections', overtime:'overtime', overtime_slip:'overtime'};
      const reviewType = reviewTypes[note.target_type];
      if (reviewType && note.target_id) { const open = document.createElement('button'); open.type = 'button'; open.className = 'tab-pill'; open.textContent = 'View request'; open.onclick = () => window.openStaffReview(reviewType, note.target_id); row.appendChild(open); }
      list.appendChild(row);
    });
  } catch (_) { list.textContent = 'Notifications could not be loaded.'; }
}


// Attendance requests are reviewed alongside the daily attendance register.
(() => {
  const view = document.getElementById('view-attendance-daily');
  if (!view) return;
  const section = document.createElement('section'); section.className = 'white-card staff-review';
  section.innerHTML = '<h2 class="card-title">Attendance requests</h2><div class="staff-review-tabs" role="group" aria-label="Request type"><button type="button" data-type="swaps">Shift swaps</button><button type="button" data-type="corrections">Attendance corrections</button><button type="button" data-type="overtime">Overtime</button></div><p class="staff-review-message" role="status"></p><div class="staff-review-list" aria-live="polite"></div>';
  view.appendChild(section);
  const list = section.querySelector('.staff-review-list'); const message = section.querySelector('.staff-review-message');
  let current = 'swaps'; let version = 0;
  const paths = {swaps:'shift-swaps', corrections:'attendance-corrections', overtime:'overtime'};
  const add = (parent, text, tag = 'p') => { const el = document.createElement(tag); el.textContent = text; parent.appendChild(el); return el; };
  const format = value => value ? new Date(value).toLocaleString() : 'Not recorded';
  const rosterText = r => r ? `${r.employee_name || r.employee} · ${r.work_date} ${r.start_time || ''}–${r.end_time || ''} ${r.shift_type || ''}` : 'Shift unavailable';
  async function load(type) {
    current = type; const stamp = ++version; message.textContent = ''; list.textContent = 'Loading requests...';
    section.querySelectorAll('[data-type]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.type === type)));
    try {
      const [rows, related] = await Promise.all([
        fetchAllApiRows(`/api/${paths[type]}/`),
        fetchAllApiRows(type === 'swaps' ? '/api/shift-rosters/' : '/api/attendance/')
      ]);
      if (stamp !== version) return;
      list.replaceChildren();
      if (!rows.length) add(list, 'No requests.');
      rows.forEach(row => {
        const card = document.createElement('article'); card.className = 'staff-review-record'; card.dataset.requestId = row.id;
        if (type === 'swaps') {
          add(card, `Requested shift: ${rosterText(row.requester_roster_display ? {...row.requester_roster_display, employee_name: row.requester_employee_name || row.requester_roster_display.employee_name} : related.find(r => String(r.id) === String(row.requester_roster)))}`);
          add(card, `Other shift: ${rosterText(row.target_roster_display ? {...row.target_roster_display, employee_name: row.target_employee_name || row.target_roster_display.employee_name} : related.find(r => String(r.id) === String(row.target_roster)))}`);
          add(card, `Reason: ${row.reason || ''}`);
        } else {
          const attendance = related.find(a => String(a.id) === String(row.attendance));
          add(card, `Employee: ${attendance?.employee_name || row.employee || 'Unavailable'} · ${attendance?.date || row.date || ''}`);
          if (type === 'corrections') {
            add(card, `Current: ${format(attendance?.clock_in)} – ${format(attendance?.clock_out)}`);
            add(card, `Proposed: ${row.proposed_clock_in ? format(row.proposed_clock_in) : 'No change'} – ${row.proposed_clock_out ? format(row.proposed_clock_out) : 'No change'}`);
            add(card, `Reason: ${row.reason || ''}`);
          } else add(card, `Calculated overtime: ${row.hours} hours · ${row.multiplier}×`);
        }
        add(card, `Status: ${row.status}`);
        const legacySwap = type === 'swaps' && (!row.requester_employee || !row.target_employee);
        if (legacySwap && row.status === 'Pending') add(card, 'Confirm participants, reject this legacy request, and create a new request.');
        if (row.status === 'Pending') {
          const actions = document.createElement('div'); actions.className = 'staff-review-actions'; card.appendChild(actions);
          ['Approved', 'Rejected'].forEach(status => {
            const button = document.createElement('button'); button.type = 'button'; button.className = 'tab-pill'; button.textContent = status === 'Approved' ? 'Approve' : 'Reject'; if (legacySwap && status === 'Approved') { button.disabled = true; button.title = 'Legacy requests must be rejected and recreated.'; } actions.appendChild(button);
            button.onclick = async () => {
              actions.querySelectorAll('button').forEach(b => b.disabled = true); message.textContent = '';
              try { await hrRequest(`/api/${paths[type]}/${encodeURIComponent(row.id)}/`, {method:'PATCH', body:JSON.stringify({status})}); await load(type); message.textContent = 'Decision saved.'; }
              catch (error) { message.textContent = error.message; actions.querySelectorAll('button').forEach(b => { b.disabled = legacySwap && b.textContent === 'Approve'; }); }
            };
          });
        }
        list.appendChild(card);
      });
    } catch (error) { if (stamp === version) { list.replaceChildren(); message.textContent = error.message || 'Requests could not be loaded.'; } }
  }
  window.openStaffReview = async (type, id) => { observer.disconnect(); switchView('attendance-daily'); await load(type); const card = [...list.querySelectorAll('[data-request-id]')].find(el => el.dataset.requestId === String(id)); if (card) { card.scrollIntoView({block:'center'}); card.setAttribute('tabindex', '-1'); card.focus(); } };
  section.querySelectorAll('[data-type]').forEach(button => button.addEventListener('click', () => load(button.dataset.type)));
  const observer = new MutationObserver(() => { if (view.classList.contains('active')) { observer.disconnect(); load(current); } });
  if (view.classList.contains('active')) load(current); else observer.observe(view, {attributes:true, attributeFilter:['class']});
  window.addEventListener('notifications:changed', () => {
    if (typeof refreshNotifBell === 'function') refreshNotifBell();
    if (document.getElementById('view-notifications')?.classList.contains('active')) loadHrNotifications();
  });
})();
