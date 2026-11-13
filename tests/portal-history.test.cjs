const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../core/templates/core/employee_portal.html'), 'utf8');
const code = template.slice(template.indexOf('    async function fetchPortalPages('), template.indexOf('    function setPortalLoadError('));

function loader(responses) {
  const calls = [];
  const context = {
    URL, window: { location: { origin: 'https://example.test' } },
    portalFetch: async (url) => { calls.push(url); return responses.shift(); },
    payload: async (response) => response.body,
    apiErrorMessage: (_data, fallback) => fallback
  };
  vm.runInNewContext(code, context);
  return { fetchPages: context.fetchPortalPages, calls };
}

test('collects every page, including relative next links', async () => {
  const { fetchPages, calls } = loader([
    { ok: true, body: { results: [{ id: 1 }], next: '?page=2' } },
    { ok: true, body: { results: [{ id: 2 }], next: null } }
  ]);
  const result = await fetchPages('/api/leaves/?page=1');
  assert.deepEqual(Array.from(result, (item) => item.id), [1, 2]);
  assert.equal(calls[1], 'https://example.test/api/leaves/?page=2');
});

test('rejects a failed later page instead of returning partial history', async () => {
  const { fetchPages } = loader([
    { ok: true, body: { results: [{ id: 1 }], next: '?page=2' } },
    { ok: false, body: {} }
  ]);
  await assert.rejects(fetchPages('/api/leaves/?page=1'));
});

test('rejects cross-origin and looping links before fetching them', async () => {
  for (const next of ['https://other.test/records', '/api/leaves/?page=1']) {
    const { fetchPages, calls } = loader([{ ok: true, body: { results: [], next } }]);
    await assert.rejects(fetchPages('/api/leaves/?page=1'));
    assert.equal(calls.length, 1);
  }
});

test('accepts an empty array and rejects malformed responses', async () => {
  const empty = loader([{ ok: true, body: [] }]);
  assert.equal((await empty.fetchPages('/api/leaves/')).length, 0);
  const malformed = loader([{ ok: true, body: {} }]);
  await assert.rejects(malformed.fetchPages('/api/leaves/'));
});

test('one failed history preserves its cards while other histories refresh', async () => {
  const refreshCode = template.slice(template.indexOf('    let requestRefreshQueue'), template.indexOf('    async function submitPortalRequest'));
  const rendered = {};
  const errors = {};
  const context = {
    fetchPortalPages: async (url) => {
      if (url.includes('advances')) throw new Error('offline');
      return [url];
    },
    setPortalLoadError: (id, failed) => { errors[id] = failed; },
    renderLeaveCards: (items) => { rendered.leave = items; },
    renderAdvanceCards: (items) => { rendered.advance = items; },
    renderComplaintCards: (items) => { rendered.complaint = items; },
    renderClaimCards: (items) => { rendered.claim = items; }
  };
  vm.runInNewContext(refreshCode, context);
  await assert.rejects(context.refreshRequestLists());
  assert.equal(rendered.advance, undefined);
  assert.equal(errors.advanceRows, true);
  assert.equal(errors.leaveRows, false);
  assert.equal(rendered.leave.length, 1);
  assert.equal(rendered.complaint.length, 1);
  assert.equal(rendered.claim.length, 1);
});
