/* Explanatory tours: navigation only, never submit forms or change records. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root.document) api.boot(root);
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const VERSION = 1;

  function progressStore(storage, account, portal) {
    const memory = new Map();
    const key = guide => `kumon.guide.v${VERSION}:${account}:${portal}:${guide}`;
    return {
      read(guide) { try { return JSON.parse(storage.getItem(key(guide))) || memory.get(guide) || null; } catch (_) { return memory.get(guide) || null; } },
      write(guide, status, step) {
        const value = {version: VERSION, status, step}; memory.set(guide, value);
        try { storage.setItem(key(guide), JSON.stringify(value)); } catch (_) { /* Private storage: use memory. */ }
      }
    };
  }

  class GuideController {
    constructor(adapter, store) { this.adapter = adapter; this.store = store; this.active = null; this.serial = 0; }
    async start(id, guide) {
      if (this.adapter.hasUnsaved()) { this.adapter.notice('Finish or save your form before starting a guide.'); return false; }
      if (this.active) this.dismiss();
      this.active = {id, guide, index: 0, missed: false};
      await this.go(0); return true;
    }
    async go(index) {
      if (!this.active) return;
      if (this.adapter.hasUnsaved()) { this.dismiss(); return; }
      const state = this.active, ticket = ++this.serial;
      this.adapter.cancelWait();
      state.index = index;
      const step = state.guide.steps[index];
      this.adapter.loading(state);
      try {
        await this.adapter.navigate(step);
        if (ticket !== this.serial) return;
        const target = await this.adapter.wait(step.target);
        if (ticket !== this.serial) return;
        if (!target) state.missed = true;
        this.adapter.show(state, step, target);
      } catch (_) {
        if (ticket === this.serial) { state.missed = true; this.adapter.show(state, step, null); }
      }
    }
    next() {
      if (!this.active) return;
      const s = this.active;
      if (s.index === s.guide.steps.length - 1) this.leave(s.missed ? 'dismissed' : 'completed');
      else return this.go(s.index + 1);
    }
    back() { if (this.active && this.active.index > 0) return this.go(this.active.index - 1); }
    dismiss() { this.leave('dismissed'); }
    leave(status) {
      if (!this.active) return;
      this.store.write(this.active.id, status, this.active.index);
      this.active = null; ++this.serial; this.adapter.cancelWait(); this.adapter.close();
    }
  }

  function cardPosition(target, width, height, viewport) {
    const gap = 12, pad = 12;
    const left = Math.max(pad, Math.min(target.left, viewport.width - width - pad));
    const below = target.bottom + gap;
    if (below + height > viewport.height - pad && target.top - height - gap < pad && target.right + width + gap <= viewport.width - pad) {
      return {left: target.right + gap, top: Math.max(pad, Math.min(target.top, viewport.height - height - pad))};
    }
    let top = below + height <= viewport.height - pad ? below : target.top - height - gap;
    if (top < pad) top = Math.max(pad, viewport.height - height - pad);
    return {left, top};
  }

  function waitForElement(doc, selector, signal, timeout = 3000) {
    return new Promise(resolve => {
      let observer, timer;
      const done = value => { observer?.disconnect(); clearTimeout(timer); signal.removeEventListener('abort', abort); resolve(value); };
      const find = () => { const el = doc.querySelector(selector); if (el && !el.hidden && el.getClientRects().length) { done(el); return true; } return false; };
      const abort = () => done(null);
      if (signal.aborted) { resolve(null); return; }
      if (find()) return;
      observer = new doc.defaultView.MutationObserver(find);
      observer.observe(doc.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden', 'style']});
      timer = setTimeout(() => done(null), timeout);
      signal.addEventListener('abort', abort, {once: true});
    });
  }

  function guidesFor(portal) {
    const step = (title, view, target, text, extra = {}) => ({title, view, target, text, ...extra});
    if (portal === 'hr') {
      const dashboard = step('Your HR workspace', 'dashboard', '.sidebar', 'Use the menu to move between employee records, attendance, requests, Pay Estimates, and account tools.');
      const people = step('Employee records', 'employee-directory', '#view-employee-directory', 'Search for an employee and review their records. HR-issued account credentials are handed to new staff for sign-in.');
      const attendance = step('Attendance and review', 'attendance-daily', '#view-attendance-daily', 'Display the office attendance QR and review daily records here. Employees scan the office code; HR reviews corrections and overtime requests.');
      const shift = step('Schedules and swaps', 'attendance-shift', '#view-attendance-shift', 'Manage dated assignments and review overlap or leave-conflict warnings. Swap decisions are available with Attendance requests in the daily register.');
      const leave = step('Leave and entitlements', 'attendance-leave', '.leave-allocation-card', 'Review requests below and manage annual allocations here. Removing an override restores any default; zero days explicitly gives no entitlement.');
      const claims = step('Claims and advances', 'claims', '#view-claims', 'Review submitted requests and their details before approving or rejecting them. The tutorial never records a decision for you.');
      const estimates = step('Advisory Pay Estimates', 'pay-estimates', '#view-pay-estimates', 'Calculate estimates for HR review. Resolve warnings and review adjustments before exporting. This does not release salary or authorize payment.');
      const security = step('Communication and account tools', 'settings', '#view-settings', 'Messages supports conversation attachments. Activity logs separate the actor from the affected employee. Enable an authenticator from your account security settings.');
      return {
        overview: {title: 'HR introduction', steps: [dashboard, people, attendance, shift, leave, claims, estimates, security]},
        attendance: {title: 'Attendance, corrections and overtime', steps: [attendance, step('Review employee requests', 'attendance-daily', '.staff-review', 'Choose corrections, swaps, or overtime to inspect pending requests. Approving a correction applies the proposed attendance change.')]},
        scheduling: {title: 'Scheduling and shift swaps', steps: [shift, step('Review a swap', 'attendance-daily', '.staff-review', 'The target employee or HR can decide a valid swap. Legacy requests without original participants must be rejected and recreated.')]},
        leave: {title: 'Leave requests and allocations', steps: [leave, step('Set the entitlement', 'attendance-leave', '.leave-allocation-form', 'Select the employee, year, leave type and days, then save when ready. Only HR can change entitlements.'), step('Review leave requests', 'attendance-leave', '#leaveRegisterTableBody', 'Approved requests reduce calendar-day balances. Insufficient balance is not automatically blocked; review the applicable policy before deciding.')]},
        claims: {title: 'Claims and advance-pay requests', steps: [claims, step('Advance requests', 'claims', '#advanceClaimsTableBody', 'Switch to the advance-pay subtab to review amounts, purposes, and repayment terms. Decisions are made by HR, outside this guide.', {subview: 'advance'})]},
        cases: {title: 'Complaints and grievances', steps: [step('Review employee concerns', 'employee-grievance', '#view-employee-grievance', 'Inspect complaints and grievances, record review status and a resolution where required. HR-only notes are not shown to employees.')]},
        estimates: {title: 'Calculate and review an estimate', steps: [estimates, step('Configure effective rules', 'pay-estimates', '#estimatePolicyForm', 'Configure effective overtime rules and paid-leave types. Missing policies or ambiguous inputs can leave an estimate incomplete.'), step('Create and review', 'pay-estimates', '#estimateForm', 'Choose the employee, period and rate. Recalculate when sources change and review each adjustment. Pending adjustments are excluded from the total.')]},
        messages: {title: 'Messages and activity logs', steps: [step('Messages', 'messages', '#view-messages', 'Select a conversation to read messages or attach an allowed file. Access is limited to authorized participants.'), step('Activity logs', 'logs', '#auditLogsTable', 'Performed by identifies the actor; Affected employee identifies the record subject. Filter events or export CSV. Historical actors may be Not recorded.')]},
        security: {title: 'Account security', steps: [step('Your account', 'profile', '#view-profile', 'Review your account information and password controls. Enable authenticator verification and save recovery codes privately. Never share them in screenshots.'), step('Preferences', 'settings', '#view-settings', 'Choose notification and display preferences. Organizational controls are shown only where permitted.')]}
      };
    }
    const attendance = step('Attendance', 'attendancePanel', '#btnClockIn', 'Use Clock In or Clock Out to scan the office QR. Manual code entry is available in the scanner. The server validates the code before recording attendance.');
    const leave = step('Leave requests and balances', 'leavePanel', '#leaveType', 'Choose your leave type, dates and reason. HR reviews the request. Your actual annual balances are shown above the form.', {segment: 'leave', pane: 'apply'});
    const advance = step('Request advance pay', 'advancePanel', '#advanceAmount', 'Enter an amount, repayment terms and purpose. Submit it for HR review and use My Advances to follow the status.', {segment: 'advance', pane: 'apply'});
    const claims = step('Expense claims', 'workflowsPanel', '#workflowContent form', 'Expense claims are inside Requests & notifications. Enter a title, category and amount, then submit for HR review.', {area: 'claims'});
    const schedule = step('My schedule and requests', 'workflowsPanel', '.workflow-tabs', 'Use these tabs to see schedules, exchange requests, attendance corrections, overtime, claims, grievances, and your inbox.', {area: 'schedule'});
    const security = step('Account and security', 'settingsPanel', '#portalMfaPill', 'Enable an authenticator if desired and store recovery codes privately. Google linking is optional and separate from authenticator verification.');
    return {
      overview: {title: 'Employee introduction', steps: [attendance, leave, advance, claims, schedule, security]},
      attendance: {title: 'Clock in and clock out', steps: [attendance, step('Clock out and history', 'attendancePanel', '#btnClockOut', 'Clock Out uses the same office-token validation. The screen shows recent attendance; errors explain when a code or action cannot be accepted.')]},
      leave: {title: 'Apply for leave', steps: [step('Your real leave balance', 'leavePanel', '.leave-allocation-card', 'Select a year and review allocated, used and remaining days. Approved leave is counted in calendar days. HR manages entitlements.'), leave, step('Follow your application', 'leavePanel', '#leaveHistorySection', 'My Requests shows the recorded status. Approval is an HR decision; this guide does not submit or approve anything.', {segment: 'leave', pane: 'history'})]},
      advance: {title: 'Request advance pay', steps: [advance, step('Track an advance', 'advancePanel', '#advanceHistorySection', 'My Advances shows submitted requests and their status. This is a request for review, not an automatic transfer of funds.', {segment: 'advance', pane: 'history'})]},
      claims: {title: 'Submit an expense claim', steps: [claims, step('Claim history', 'workflowsPanel', '#workflowContent .workflow-list', 'Your submitted claims appear here. Open details to check the amount and review status. No receipt upload is provided by this form.', {area: 'claims'})]},
      schedule: {title: 'View schedules and swap shifts', steps: [schedule, step('Request an exchange', 'workflowsPanel', '#workflowContent form', 'Choose your assignment and an eligible shift on the same date. The target employee or HR can decide the swap after validation.', {area: 'swaps'})]},
      corrections: {title: 'Corrections and overtime', steps: [step('Request a correction', 'workflowsPanel', '#workflowContent form', 'Select your attendance record, provide at least one proposed time and explain the change. HR approval applies a correction.', {area: 'corrections'}), step('Request overtime review', 'workflowsPanel', '#workflowContent form', 'Choose completed attendance. Hours and multiplier are determined by the configured policy, not entered by you. HR reviews the request.', {area: 'overtime'})]},
      cases: {title: 'Complaints and grievances', steps: [step('Contact HR about a concern', 'complaintPanel', '#complaintSubject', 'Submit the category, subject and details of your concern. My Reports shows its status and any employee-visible response.', {segment: 'complaint', pane: 'apply'}), step('File a grievance', 'workflowsPanel', '#workflowContent form', 'Use Grievances to submit and follow a formal concern. HR reviews it and records a resolution; internal notes remain private.', {area: 'grievances'})]},
      messages: {title: 'Messages and notifications', steps: [step('Messages and attachments', 'messagesPanel', '#chatComposerInput', 'Choose a conversation first. You can send text or an allowed PDF, image, or text attachment up to 5 MB.'), step('Your inbox', 'workflowsPanel', '#workflowContent', 'Open a notification to inspect its related record, or mark it as read. Updates arrive while connected, with periodic refresh as a fallback.', {area: 'notifications'})]},
      security: {title: 'Account security', steps: [security, step('Optional Google linking', 'settingsPanel', '#portalGoogleAccountStatus', 'A Google account can be linked optionally. Keep using your password if you do not link one; authenticator settings are separate.')]}
    };
  }

  function formTracker() {
    const states = new Map();
    const state = form => {
      if (!states.has(form)) states.set(form, {revision: 0, clean: 0, pending: []});
      return states.get(form);
    };
    return {
      change(form) { state(form).revision++; },
      reset(form) { const s = state(form); s.clean = ++s.revision; },
      start(form) { const s = state(form); s.pending.push(s.revision); },
      end(form, success) {
        const s = state(form), revision = s.pending.shift();
        if (success && revision !== undefined && s.revision === revision) s.clean = revision;
      },
      hasUnsaved() {
        for (const [form, s] of states) {
          if (!form.isConnected) { states.delete(form); continue; }
          if (s.pending.length || s.revision !== s.clean) return true;
        }
        return false;
      }
    };
  }

  function boot(win) {
    const doc = win.document, context = doc.getElementById('walkthroughContext');
    if (!context || win.KumonGuide) return;
    const portal = context.dataset.portal, account = context.dataset.account;
    if (!account || !['hr', 'employee'].includes(portal)) return;
    let storage; try { storage = win.localStorage; } catch (_) { storage = null; }
    const store = progressStore(storage, account, portal), guides = guidesFor(portal);
    let card, ring, target, waitAbort, returnFocus, menu, invite, navigating = false;
    const dirty = formTracker();
    const editableForm = form => form && !form.matches('.workflow-date-filters, [data-guide-ignore-dirty]');
    const make = (tag, text) => { const el = doc.createElement(tag); if (text) el.textContent = text; return el; };
    const visible = el => el && el.isConnected && !el.hidden && el.getClientRects().length;
    const hasUnsaved = () => dirty.hasUnsaved() || [...doc.querySelectorAll('form button[type="submit"]:disabled')].some(visible);
    function clean() { card?.remove(); ring?.remove(); card = ring = target = null; }
    function position() {
      if (!card) return;
      const vv = win.visualViewport;
      const viewport = {width: vv?.width || win.innerWidth, height: vv?.height || win.innerHeight};
      if (visible(target)) {
        const box = target.getBoundingClientRect();
        Object.assign(ring.style, {left: `${Math.max(0, box.left - 4)}px`, top: `${Math.max(0, box.top - 4)}px`, width: `${Math.min(box.width + 8, viewport.width)}px`, height: `${Math.min(box.height + 8, viewport.height)}px`});
        const pos = cardPosition(box, card.offsetWidth, card.offsetHeight, viewport);
        card.style.left = `${pos.left}px`; card.style.top = `${pos.top}px`;
      } else { if (ring) ring.hidden = true; card.style.left = '12px'; card.style.top = '12px'; }
    }
    function closeMenu() { menu.hidden = true; launcher.setAttribute('aria-expanded', 'false'); }
    const controller = new GuideController({
      hasUnsaved, notice: text => { menu.hidden = false; menuStatus.textContent = text; launcher.setAttribute('aria-expanded', 'true'); },
      cancelWait: () => { waitAbort?.abort(); },
      loading: state => { invite?.remove(); clean(); card = make('section'); card.className = 'guide-card'; card.setAttribute('role', 'status'); card.textContent = `Opening ${state.guide.steps[state.index].title}...`; doc.body.append(card); position(); },
      navigate: async step => {
        navigating = true;
        try {
          if (portal === 'hr') {
            if (typeof win.switchView !== 'function') throw new Error('Navigation unavailable');
            win.switchView(step.view);
            // Use only existing navigation, never click a business action.
            if (step.subview === 'advance' && typeof win.switchClaimsTab === 'function') win.switchClaimsTab('advance');
          } else {
            win.switchPortalTab(step.view);
            if (step.area) {
              if (typeof win.openEmployeeWorkflowArea !== 'function') throw new Error('Requests unavailable');
              await win.openEmployeeWorkflowArea(step.area);
            }
            if (step.segment) win.setSegmentTab(step.segment, step.pane);
          }
        } finally { navigating = false; }
      },
      wait: selector => { waitAbort = new AbortController(); return waitForElement(doc, selector, waitAbort.signal); },
      show: (state, step, element) => {
        clean(); target = element;
        card = make('section'); card.className = 'guide-card'; card.setAttribute('role', 'dialog'); card.setAttribute('aria-modal', 'false'); card.setAttribute('aria-labelledby', 'guideTitle');
        card.append(make('p', `${state.index + 1} of ${state.guide.steps.length} · ${state.guide.title}`));
        const title = make('h2', step.title); title.id = 'guideTitle'; card.append(title);
        const text = make('p', element ? step.text : 'This control is not available here. Continue to skip this step, or close the guide and try again later.'); text.setAttribute('aria-live', 'polite'); card.append(text);
        const footer = make('div'); footer.className = 'guide-actions';
        const back = make('button', 'Back'); back.disabled = state.index === 0; back.onclick = () => controller.back();
        const skip = make('button', 'Skip guide'); skip.onclick = () => controller.dismiss();
        const next = make('button', state.index === state.guide.steps.length - 1 ? 'Finish' : 'Next'); next.onclick = () => controller.next();
        [back, skip, next].forEach(b => { b.type = 'button'; footer.append(b); }); card.append(footer);
        ring = make('div'); ring.className = 'guide-highlight'; ring.setAttribute('aria-hidden', 'true'); ring.hidden = !element; doc.body.append(ring, card);
        if (element) element.scrollIntoView({block: 'center', behavior: 'instant'});
        position(); next.focus({preventScroll: true});
      },
      close: () => { const restore = card?.contains(doc.activeElement); clean(); if (restore && visible(returnFocus)) returnFocus.focus({preventScroll: true}); }
    }, store);
    const launcher = make('button', 'Help'); launcher.type = 'button'; launcher.className = 'guide-launcher'; launcher.setAttribute('aria-controls', 'guideMenu'); launcher.setAttribute('aria-expanded', 'false'); launcher.setAttribute('aria-label', 'Help and guided walkthroughs');
    if (portal === 'employee') doc.querySelector('.portal-top-nav-right')?.append(launcher); else doc.body.append(launcher);
    menu = make('section'); menu.id = 'guideMenu'; menu.className = 'guide-menu'; menu.hidden = true; menu.setAttribute('aria-label', 'Guided walkthroughs');
    menu.append(make('h2', 'Help & walkthroughs'));
    const menuStatus = make('p', 'Choose a short introduction or a task guide. Guides explain controls without submitting or changing anything.'); menuStatus.setAttribute('role', 'status'); menu.append(menuStatus);
    const buttons = [];
    for (const [id, guide] of Object.entries(guides)) {
      const b = make('button', guide.title); b.type = 'button'; b.onclick = async () => { returnFocus = launcher; closeMenu(); await controller.start(id, guide); }; buttons.push(b); menu.append(b);
    }
    const later = make('button', 'Close'); later.type = 'button'; later.onclick = () => { closeMenu(); launcher.focus(); }; menu.append(later); doc.body.append(menu);
    launcher.onclick = () => { controller.dismiss(); menu.hidden = !menu.hidden; launcher.setAttribute('aria-expanded', String(!menu.hidden)); if (!menu.hidden) buttons[0].focus(); };
    win.KumonGuide = {start(id = 'overview') { if (!guides[id]) return; returnFocus = doc.activeElement === doc.body ? launcher : doc.activeElement; closeMenu(); return controller.start(id, guides[id]); }, dismiss: () => controller.dismiss()};
    win.startTour = () => win.KumonGuide.start('overview');
    doc.getElementById('replayTourBtn')?.addEventListener('click', win.startTour);
    doc.addEventListener('keydown', e => { if (e.key === 'Escape') { controller.dismiss(); closeMenu(); } });
    doc.addEventListener('input', e => { if (editableForm(e.target.form) && !e.target.closest('.guide-menu, .guide-card')) { dirty.change(e.target.form); controller.dismiss(); } }, true);
    doc.addEventListener('change', e => { if (editableForm(e.target.form) && !e.target.closest('.guide-menu, .guide-card')) { dirty.change(e.target.form); controller.dismiss(); } }, true);
    doc.addEventListener('reset', e => { queueMicrotask(() => { if (!e.defaultPrevented) dirty.reset(e.target); }); }, true);
    doc.addEventListener('guide:save-start', e => { if (editableForm(e.target)) { dirty.start(e.target); controller.dismiss(); } }, true);
    doc.addEventListener('guide:save-end', e => { if (editableForm(e.target)) dirty.end(e.target, e.detail?.success === true); }, true);
    doc.addEventListener('click', e => { if (controller.active && !navigating && e.target.closest('.portal-tab, .nav-link, .tab-pill, .workflow-tabs button') && !e.target.closest('.guide-card')) controller.dismiss(); }, true);
    win.addEventListener('resize', position); win.addEventListener('scroll', position, true); win.visualViewport?.addEventListener('resize', position);
    win.addEventListener('pagehide', () => controller.dismiss());
    // Invitation only: never navigate away from the user's page automatically.
    if (!store.read('overview')) {
      invite = make('aside'); invite.className = 'guide-invite'; invite.setAttribute('aria-label', 'Walkthrough invitation');
      invite.append(make('p', `New to the ${portal === 'hr' ? 'HR' : 'employee'} portal? Take a short introduction, or find it later under Help.`));
      const start = make('button', 'Start introduction'); start.type = 'button'; start.onclick = () => { invite.remove(); win.KumonGuide.start(); };
      const skip = make('button', 'Not now'); skip.type = 'button'; skip.onclick = () => { store.write('overview', 'dismissed', 0); invite.remove(); };
      invite.append(start, skip); doc.body.append(invite);
    }
  }
  return {VERSION, progressStore, GuideController, cardPosition, waitForElement, guidesFor, formTracker, boot};
});
