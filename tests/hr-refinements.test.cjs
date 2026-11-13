const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
function setup() {
  const elements = {};
  const makeForm = () => ({ elements: { status: { value: 'Pending' }, resolution: { value: '' }, internal_notes: { value: '' } }, listeners: {}, addEventListener(n, f) { this.listeners[n] = f; } });
  const list = elements.grievanceCaseList = { children: [], set innerHTML(v) { this.children = []; }, appendChild(c) { this.children.push(c); } };
  for (const id of ['grievanceOpenCount','grievanceMediationCount','grievanceResolvedCount']) elements[id] = {};
  elements.grievComplainant = { value: '', set innerHTML(v) {}, add() {} };
  for (const id of ['hrGrievancesTab','hrComplaintsTab']) elements[id] = { classList: { toggle() {} } };
  const document = { getElementById: id => elements[id], createElement(tag) {
    if (tag !== 'article') return {};
    const form = makeForm();
    return { form, dataset: {}, set innerHTML(v) {}, querySelector() { return form; }, insertBefore(n) { this.notice = n.textContent; }, appendChild() {} };
  } };
  let rows = { grievances: [{ id: 1, status: 'Pending', internal_notes: '', resolution: '' }], complaints: [], employees: [] };
  let patch = async () => ({ ok: true, status: 204 });
  let fetchRows = async url => rows[url.split('/')[2]];
  const ctx = vm.createContext({ document, Option: function(){}, escapeHtml: String, showToast() {}, confirm: () => true,
    fetchAllApiRows: url => fetchRows(url), apiFetch: (...args) => patch(...args),
    FormData: function(form) { this.get = key => form.elements[key].value; } });
  const source = fs.readFileSync('static/js/hr-workflows.js', 'utf8').split('let estimateRecords')[0];
  vm.runInContext(source, ctx);
  return { ctx, list, setRows: value => { rows = value; }, setPatch: value => { patch = value; }, setFetch: value => { fetchRows = value; } };
}

test('drafts survive polling, register changes, and report server changes', async () => {
  const t = setup(); await t.ctx.loadGrievanceView();
  let form = t.list.children[0].form;
  form.elements.internal_notes.value = 'draft'; form.listeners.input();
  t.setRows({ grievances: [{ id: 1, status: 'Pending', internal_notes: 'server', resolution: '' }], complaints: [], employees: [] });
  await t.ctx.loadGrievanceView();
  assert.equal(t.list.children[0].form.elements.internal_notes.value, 'draft');
  assert.match(t.list.children[0].notice, /changed on the server/);
  t.ctx.selectHrCaseRegister('complaints'); t.ctx.selectHrCaseRegister('grievances');
  assert.equal(t.list.children[0].form.elements.internal_notes.value, 'draft');
});

test('edits made during a save survive, including reverting to original value', async () => {
  const t = setup(); await t.ctx.loadGrievanceView();
  const form = t.list.children[0].form; const request = deferred();
  t.setPatch(() => request.promise);
  form.elements.internal_notes.value = 'submitted'; form.listeners.input();
  const saving = form.listeners.submit({ preventDefault() {}, currentTarget: form });
  form.elements.internal_notes.value = ''; form.listeners.input();
  t.setRows({ grievances: [{ id: 1, status: 'Pending', internal_notes: 'submitted', resolution: '' }], complaints: [], employees: [] });
  request.resolve({ ok: true, status: 204 }); await saving;
  assert.equal(t.list.children[0].form.elements.internal_notes.value, '');
});

test('older case reads cannot overwrite newer results', async () => {
  const t = setup(); const older = deferred(); let calls = 0;
  t.setFetch(url => {
    if (url.includes('/grievances/')) return ++calls === 1 ? older.promise : Promise.resolve([{ id: 1, status: 'Resolved', internal_notes: 'new' }]);
    return Promise.resolve([]);
  });
  const first = t.ctx.loadGrievanceView(); await t.ctx.loadGrievanceView();
  older.resolve([{ id: 1, status: 'Pending', internal_notes: 'old' }]); await first;
  assert.equal(vm.runInContext('hrCases.grievances[0].internal_notes', t.ctx), 'new');
});

test('notification badge uses count endpoint and ignores stale responses', async () => {
  const pill = { style: {} }, requests = [];
  const ctx = vm.createContext({ document: { getElementById: () => pill }, apiFetch: url => { assert.equal(url, '/api/notifications/unread-count/'); const d = deferred(); requests.push(d); return d.promise; } });
  const source = fs.readFileSync('static/js/dashboard.js', 'utf8');
  vm.runInContext(source.slice(source.indexOf('let notifBellRequestVersion'), source.indexOf('// Bell opens')), ctx);
  const first = ctx.refreshNotifBell(), second = ctx.refreshNotifBell();
  requests[1].resolve({ ok: true, json: async () => ({ unread_count: 125 }) }); await second;
  requests[0].resolve({ ok: true, json: async () => ({ unread_count: 1 }) }); await first;
  assert.equal(pill.textContent, '125'); assert.equal(pill.style.display, '');
});
