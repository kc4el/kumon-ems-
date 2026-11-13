const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('import credentials are masked, copied on request, and explicitly cleared', async () => {
  const element = () => ({ children: [], append(...items) { this.children.push(...items); }, replaceChildren() { this.children = []; }, setAttribute() {} });
  const section = element(), list = element(); section.hidden = true;
  let copied;
  const context = vm.createContext({ document: {
    getElementById: id => id === 'settingsImportCredentials' ? section : list,
    createElement: element,
  }, navigator: { clipboard: { writeText: async value => { copied = value; } } }, location: { origin: 'https://example.test' }, showToast() {} });
  const source = fs.readFileSync('static/js/dashboard.js', 'utf8');
  vm.runInContext(source.slice(source.indexOf('function clearSettingsImportCredentials()'), source.indexOf('let settingsImportInFlight')), context);
  context.renderSettingsImportCredentials([{employee_name: '<Test User>', employee_id: 'EMP-TEST', temporary_password: 'test-only-value'}]);
  const [label, password, reveal, copy] = list.children[0].children;
  assert.equal(label.textContent, '<Test User> — EMP-TEST');
  assert.equal(password.type, 'password'); assert.equal(password.readOnly, true);
  assert.equal(copied, undefined);
  reveal.onclick(); assert.equal(password.type, 'text');
  await copy.onclick(); assert.match(copied, /Employee ID: EMP-TEST/);
  context.clearSettingsImportCredentials();
  assert.equal(list.children.length, 0); assert.equal(section.hidden, true);
});

for (const ok of [true, false]) {
  test(`preferences notify the guide of ${ok ? 'successful' : 'failed'} saves`, async () => {
    const events = [], submit = {disabled: false};
    const form = { querySelector: () => submit, dispatchEvent: event => events.push(event) };
    const context = vm.createContext({
      document: { getElementById: () => null },
      empPageSize: {value:'10'}, empHighContrast:{checked:false},
      CustomEvent: function(type, options) { this.type = type; this.detail = options.detail; },
      portalFetch: async () => ({ok}), payload: async () => ({}), showStatus() {},
    });
    const source = fs.readFileSync('core/templates/core/employee_portal.html', 'utf8');
    vm.runInContext(source.slice(source.indexOf('async function submitPrefs('), source.indexOf('async function employeeLogout(')), context);
    await context.submitPrefs({preventDefault() {}, target:form});
    assert.equal(events[0].type, 'guide:save-start');
    assert.equal(events[1].type, 'guide:save-end');
    assert.equal(events[1].detail.success, ok);
    assert.equal(submit.disabled, false);
  });
}
