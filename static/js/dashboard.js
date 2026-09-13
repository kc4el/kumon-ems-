/* ==========================================================================
   Kumon EMS - Interactive Logic & State Management
   ========================================================================== */


document.addEventListener('DOMContentLoaded', () => {
  initBrandLogo();
  initNavigation();
  loadDashboardSummary();
  loadEmployeeDirectory();
  loadClaimStatuses();
  updateBatchApproveCount();
  loadAdvancesView();
  loadMessagesForConversation('sarah');
  loadAttendanceView();
  loadShiftRosterView();
  loadAuditView();
  initDashboardWidgets();
  loadActivityFeed();
  refreshNotifBell();
  initTour();
});

// Bell counts live unread notifications. Same apiFetch + pill style as inbox.
// Fails quiet on login page: apiFetch already skips redirect there.
async function refreshNotifBell() {
  const pill = document.getElementById('notifUnreadPill');
  try {
    const res = await apiFetch('/api/notifications/', { headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error('notif unavailable');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    const unread = rows.filter((n) => !n.is_read).length;
    if (pill) {
      pill.textContent = String(unread);
      pill.style.display = unread > 0 ? '' : 'none';
    }
  } catch (error) {
    if (pill) pill.style.display = 'none';
  }
}

// Bell opens the inbox view. Same navigation pattern as other header tools.
function openNotifInbox(e) {
  if (e) e.preventDefault();
  refreshNotifBell();
  if (typeof switchView === 'function') switchView('messages');
  else showToast('Inbox view is not available here.');
}

// ==========================================================================
// Session auth + API mode badge (R2/R8)
// Same-origin dashboard calls use session auth + CSRF; DRF tokens stay for
// scripts/operator use. apiFetch is the single helper for ALL API calls:
// it sends cookies + CSRF and bounces logged-out users to /login/?next=.
// setApiMode drives the #apiModeBadge (LIVE green / DEMO DATA amber).
// ==========================================================================
function apiFetch(url, options = {}) {
  const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1];
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    if (csrf) headers['X-CSRFToken'] = headers['X-CSRFToken'] || csrf;
  } else if (csrf) {
    headers['X-CSRFToken'] = headers['X-CSRFToken'] || csrf;
  }
  return fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers,
  }).then((res) => {
    // Logged-out viewers bouncing around /login/?next=/login/ loop forever:
    // serve the login page instead of redirecting to itself.
    if ((res.status === 401 || res.status === 403) && window.location.pathname.startsWith('/login')) return res;
    if (res.status === 401) { window.location.href = "/login/?next=" + encodeURIComponent(window.location.pathname); throw new Error("auth"); }
    if (res.status === 403) { window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname); throw new Error('auth'); }
    return res;
  });
}

function setApiMode(mode) {
  document.body.dataset.api = mode;
  const badge = document.getElementById('apiModeBadge');
  if (badge) {
    const live = mode === 'live';
    badge.textContent = live ? 'LIVE' : 'DEMO DATA';
    badge.className = 'penpot-badge ' + (live ? 'badge-present' : 'badge-pending');
  }
}

// Automatic Logo Path Resolver for file:// and http:// protocols
function initBrandLogo() {
  const isFileProtocol = window.location.protocol === 'file:';
  const currentPath = window.location.pathname.toLowerCase();
  
  const logoImgs = document.querySelectorAll('.brand-logo-img');
  logoImgs.forEach(img => {
    let bestSrc = '/static/images/kumon-logo.png';
    if (isFileProtocol) {
      if (currentPath.includes('templates') || currentPath.includes('core')) {
        bestSrc = '../../../static/images/kumon-logo.png';
      } else if (currentPath.includes('pages')) {
        bestSrc = '../static/images/kumon-logo.png';
      } else {
        bestSrc = 'static/images/kumon-logo.png';
      }
    }
    img.src = bestSrc;
    img.onerror = () => {
      if (img.src.includes('../../../static') || img.src.includes('../../static')) {
        img.src = '../static/images/kumon-logo.png';
      } else if (img.src.includes('static/')) {
        img.src = '/static/images/kumon-logo.png';
      } else {
        img.src = 'images/kumon-logo.png';
      }
    };
  });
}


// View Navigation Mapping
const viewBreadcrumbs = {
  'dashboard': { active: 'Dashboard' },
  'employee-directory': { active: 'Employee Directory' },
  'employee-manage': { root: 'Employees', active: 'Manage Staff' },
  'employee-grievance': { root: 'Employees', active: 'Grievance Tracker' },
  'attendance-daily': { root: 'Attendance', active: 'Daily Attendance & Time Log' },
  'attendance-shift': { root: 'Attendance', active: 'Shift Scheduling & Roster' },
  'attendance-leave': { root: 'Attendance', active: 'Leave & Absence Management' },
  'claims': { active: 'Claims & Reimbursements' },
  'messages': { active: 'Messages & Channels' },
  'logs': { root: 'Security & Audit', active: 'Audit & Activity Logs' },
  'profile': { root: 'Security & Audit', active: 'Audit & Activity Logs' },
  'my-details': { root: 'Security & Audit', active: 'Audit & Activity Logs' },
  'reports': { active: 'Reports & Analytics' }
};


function initNavigation() {
  const navLinks = document.querySelectorAll('.nav-link[data-view]');
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetView = link.getAttribute('data-view');
      if (targetView) {
        switchView(targetView);
      }
    });
  });
}


function switchView(viewName) {
  // Update sidebar active link
  document.querySelectorAll('.nav-link').forEach(link => {
    const dataView = link.getAttribute('data-view');
    if (dataView === viewName ||
       (viewName.startsWith('employee') && dataView === 'employee-directory') ||
       (viewName.startsWith('attendance') && dataView === 'attendance-daily') ||
       (viewName === 'claims' && dataView === 'claims') ||
       (viewName === 'messages' && dataView === 'messages') ||
       ((viewName === 'logs' || viewName === 'profile' || viewName === 'my-details') && dataView === 'logs')) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Hide all view panels
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.remove('active');
  });

  // Handle header visibility and layout mode for messages
  const topHeader = document.querySelector('.top-header-bar');
  const mainArea = document.querySelector('.main-content-area');
  if (viewName === 'messages') {
    if (topHeader) topHeader.style.display = 'none';
    if (mainArea) mainArea.classList.add('messages-active-area');
  } else {
    if (topHeader) topHeader.style.display = 'flex';
    if (mainArea) mainArea.classList.remove('messages-active-area');
  }

  // Show target view panel or placeholder
  const targetPanel = document.getElementById(`view-${viewName}`);
  if (targetPanel) {
    targetPanel.classList.add('active');
    if (viewName === 'messages') {
      loadMessagesForConversation(activeConversationKey);
    }
  } else {
    // Show placeholder view with specific title
    const placeholderPanel = document.getElementById('view-placeholder');
    const placeholderTitle = document.getElementById('placeholderTitle');
    if (placeholderPanel && placeholderTitle) {
      placeholderTitle.textContent = viewName.replace('-', ' ').toUpperCase();
      placeholderPanel.classList.add('active');
      const payrollWrap = document.getElementById('payrollLiveWrap');
      if (payrollWrap) {
        if (viewName.includes('payroll')) {
          payrollWrap.style.display = 'block';
          loadPayrollView();
        } else {
          payrollWrap.style.display = 'none';
        }
      }
    }
  }

  // Update breadcrumb trail
  const breadcrumbTrail = document.getElementById('breadcrumbTrail');
  if (breadcrumbTrail && viewBreadcrumbs[viewName]) {
    const info = viewBreadcrumbs[viewName];
    if (info.root) {
      breadcrumbTrail.innerHTML = `<span class="bc-root">${info.root}</span> <span class="bc-slash">/</span> <span class="bc-page">${info.active}</span>`;
    } else {
      breadcrumbTrail.innerHTML = `<span class="bc-page">${info.active}</span>`;
    }
  }

  // Smooth scroll to top of viewport
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// D4: keyboard shortcuts (view jumps only) + "?" cheat sheet. Single-key
// map; ignored while typing. NOTE: the cheat-sheet modal reuses the repo's
// existing .modal-backdrop/.modal-card classes (no plain ".modal" exists).
const KUMON_SHORTCUTS = {
  "g d": "dashboard",
  "g e": "employee-directory",
  "g a": "attendance-daily",
  "g s": "attendance-shift",
  "g l": "attendance-leave",
  "g c": "claims",
  "g m": "messages",
};
let kumonKeyPrefix = null;
document.addEventListener("keydown", (e) => {
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || e.target.isContentEditable) return;
  if (e.key === "?") { toggleShortcutHelp(); return; }
  if (e.key === "Escape") { hideShortcutHelp(); if (kumonTourIndex >= 0) endTour(); kumonKeyPrefix = null; return; }
  const seq = kumonKeyPrefix ? kumonKeyPrefix + " " + e.key.toLowerCase() : null;
  kumonKeyPrefix = null;
  if (seq && KUMON_SHORTCUTS[seq]) { switchView(KUMON_SHORTCUTS[seq]); return; }
  if (e.key.toLowerCase() === "g" && !e.ctrlKey && !e.metaKey && !e.altKey) kumonKeyPrefix = "g";
});
function toggleShortcutHelp() {
  const el = document.getElementById("shortcutHelp");
  if (el) el.classList.toggle("active");
}
function hideShortcutHelp() {
  const el = document.getElementById("shortcutHelp");
  if (el) el.classList.remove("active");
}

// D5: dashboard widget visibility + order, persisted in localStorage.
const KUMON_WIDGETS_KEY = "kumon.dashboardWidgets.v1";
function initDashboardWidgets() {
  const cards = [...document.querySelectorAll("#view-dashboard .kpi-card")];
  if (!cards.length) return;
  cards.forEach((card, i) => {
    if (!card.dataset.widget) {
      const text = (card.innerText != null ? card.innerText : card.textContent) || "";
      const label = (text.split("\n")[0] || ("card-" + i)).trim();
      card.dataset.widget = label.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    }
  });
  const saved = readWidgetPrefs();
  if (saved) {
    const byId = Object.fromEntries(cards.map((c) => [c.dataset.widget, c]));
    const grid = cards[0].parentElement;
    saved.order.forEach((id) => { if (byId[id]) grid.appendChild(byId[id]); });
    (saved.hidden || []).forEach((id) => { if (byId[id]) byId[id].style.display = "none"; });
  }
  renderWidgetSettings();
}
function readWidgetPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(KUMON_WIDGETS_KEY));
    if (saved && Array.isArray(saved.order)) return { order: saved.order, hidden: saved.hidden || [] };
  } catch (e) { /* private mode: fall back to default layout */ }
  return null;
}
function writeWidgetPrefs() {
  const cards = [...document.querySelectorAll("#view-dashboard .kpi-card")];
  const prefs = {
    order: cards.map((c) => c.dataset.widget),
    hidden: cards.filter((c) => c.style.display === "none").map((c) => c.dataset.widget),
  };
  try { localStorage.setItem(KUMON_WIDGETS_KEY, JSON.stringify(prefs)); } catch (e) { /* degrade silently */ }
}
function renderWidgetSettings() {
  const view = document.getElementById("view-dashboard");
  if (!view || document.getElementById("widgetSettings")) return;
  const details = document.createElement("details");
  details.id = "widgetSettings";
  const summary = document.createElement("summary");
  summary.textContent = "Customize dashboard";
  details.appendChild(summary);
  const list = document.createElement("div");
  list.id = "widgetSettingsList";
  details.appendChild(list);
  view.prepend(details);
  refreshWidgetSettings();
}
function refreshWidgetSettings() {
  const list = document.getElementById("widgetSettingsList");
  if (!list) return;
  list.innerHTML = "";
  const cards = [...document.querySelectorAll("#view-dashboard .kpi-card")];
  cards.forEach((card) => {
    const id = card.dataset.widget;
    const row = document.createElement("div");
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = card.style.display !== "none";
    box.setAttribute("aria-label", "Show " + id);
    box.addEventListener("change", () => {
      card.style.display = box.checked ? "" : "none";
      writeWidgetPrefs();
      refreshWidgetSettings();
    });
    label.appendChild(box);
    label.appendChild(document.createTextNode(" " + id));
    row.appendChild(label);
    const up = document.createElement("button");
    up.type = "button";
    up.textContent = "↑";
    up.setAttribute("aria-label", "Move " + id + " up");
    up.addEventListener("click", () => { moveWidget(card, -1); });
    const down = document.createElement("button");
    down.type = "button";
    down.textContent = "↓";
    down.setAttribute("aria-label", "Move " + id + " down");
    down.addEventListener("click", () => { moveWidget(card, 1); });
    row.appendChild(up);
    row.appendChild(down);
    list.appendChild(row);
  });
}
function moveWidget(card, dir) {
  const grid = card.parentElement;
  const sib = dir < 0 ? card.previousElementSibling : card.nextElementSibling;
  if (!sib || !sib.classList.contains("kpi-card")) return;
  grid.insertBefore(card, dir < 0 ? sib : sib.nextElementSibling);
  writeWidgetPrefs();
  refreshWidgetSettings();
}

// D6: "Today" activity feed from the live audit log. Uses raw fetch (not
// apiFetch) so a logged-out 401/403 renders "Activity unavailable." instead
// of triggering apiFetch's login redirect; the feed never bounces to login.
async function loadActivityFeed() {
  const list = document.getElementById("activityFeedList");
  if (!list) return;
  try {
    const res = await fetch("/api/audit-logs/?page_size=20", { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("feed failed");
    const payload = await res.json();
    const rows = payload.results || payload || [];
    list.innerHTML = rows.length
      ? rows.map((r) => `<li>${escapeHtml(String(r.action || "update"))} <span>${escapeHtml(String(r.timestamp || "").slice(0, 16).replace("T", " "))}</span></li>`).join("")
      : "<li>No activity yet today.</li>";
  } catch (e) { list.innerHTML = "<li>Activity unavailable.</li>"; }
}

// Full-coverage guided tour: one stop per view, demo-only controls disclosed.
// (Two dashboard stops in a row are deliberate — second covers Customize +
// feed + badge. Final step returns to the directory as the natural home.)
const KUMON_TOUR_KEY = "kumon.tourSeen.v1";
const KUMON_TOUR_STEPS = [
  { view: "dashboard", text: "Welcome! This is your home screen. Here you can see at a glance how many employees you have, who is on leave, and what needs your attention today. Those little arrow buttons jump you straight to the right page." },
  { view: "dashboard", text: "Make this screen yours! Press Customize to show, hide, or reorder these cards however you like. The Today box shows the latest goings-on, and the little badge tells you whether the numbers are fresh from the system or just samples." },
  { view: "employee-directory", text: "This is your people list — everyone who works here, all in one place you can search. Tap any name to open their details.", demo: "Full staff profiles and chat messaging are on the way soon!" },
  { view: "employee-manage", text: "This is where people changes happen. The three tabs at the top switch between promoting someone, moving them to another team, or removing them. Further down, the leaving form with its simple yes-or-no questions files a resignation." },
  { view: "employee-grievance", text: "If someone raises a concern, this is where it gets looked after — you can track each case and schedule sit-downs to sort things out.", demo: "File with the form above; cases land in the team chat thread." },
  { view: "attendance-daily", text: "This is the daily time sheet. Use the little arrows to hop between days and see who clocked in and out, and when.", demo: "Downloading this as a file is coming soon." },
  { view: "attendance-shift", text: "This is the roster board. Pick a date (or just press Today), then press Assign to place someone on the morning, evening, or night shift. If you see a little warning flag, it means that person already has an approved leave that day." },
  { view: "attendance-leave", text: "Time-off requests live here. Press the big button to file one yourself, and you can approve or say no to other people's requests from the same list — they will get a message telling them what you decided." },
  { view: "claims", text: "Money stuff! This is where repayment requests land. You can search for any request and approve a whole bunch at once with one press.", demo: "History pages below load live from the server." },
  { view: "messages", text: "This is the team chat. Pick a conversation on the left, type on the right — whatever you send goes out under your own name, automatically." },
  { view: "logs", text: "Think of this as the diary of everything that happens in the system. Those little category buttons let you look at just people changes, leaves, money, rosters, or concerns.", demo: "Later pages load live from the server." },
  { view: "employee-directory", text: "And that's the whole tour — well done! Remember, you can press the ? key anytime to see handy keyboard shortcuts, and there's a Replay button back on the home screen whenever you want a refresher." },
];
let kumonTourIndex = -1;
function startTour() {
  try { localStorage.removeItem(KUMON_TOUR_KEY); } catch (e) {}
  kumonTourIndex = -1; nextTourStep();
}
function nextTourStep() {
  kumonTourIndex += 1;
  if (kumonTourIndex >= KUMON_TOUR_STEPS.length) { endTour(); return; }
  const step = KUMON_TOUR_STEPS[kumonTourIndex];
  switchView(step.view);
  showTourBubble(step, kumonTourIndex + 1, KUMON_TOUR_STEPS.length);
}
function endTour() {
  kumonTourIndex = -1;
  const b = document.getElementById("tourBubble");
  if (b) b.remove();
  try { localStorage.setItem(KUMON_TOUR_KEY, "1"); } catch (e) {}
}
function showTourBubble(step, n, total) {
  const old = document.getElementById("tourBubble");
  if (old) old.remove();
  const b = document.createElement("div");
  b.id = "tourBubble";
  b.className = "modal-card";
  b.setAttribute("role", "dialog");
  b.setAttribute("aria-label", "Onboarding tour step " + n + " of " + total);
  const head = document.createElement("div");
  head.className = "modal-head";
  const badge = document.createElement("span");
  badge.className = "penpot-badge badge-onduty";
  badge.textContent = "Step " + n + " of " + total;
  const title = document.createElement("h3");
  title.textContent = "Welcome tour";
  head.appendChild(title);
  head.appendChild(badge);
  const p = document.createElement("p");
  p.className = "tour-text";
  p.textContent = step.text;
  const dots = document.createElement("div");
  dots.className = "tour-dots";
  dots.setAttribute("aria-hidden", "true");
  for (let i = 1; i <= total; i++) {
    const d = document.createElement("span");
    d.className = "tour-dot" + (i === n ? " on" : "") + (i < n ? " done" : "");
    dots.appendChild(d);
  }
  const foot = document.createElement("div");
  foot.className = "modal-foot";
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "btn-black-sm";
  skip.textContent = "Skip";
  skip.addEventListener("click", endTour);
  const next = document.createElement("button");
  next.type = "button";
  next.className = "btn-blue-sm";
  next.textContent = n >= total ? "Finish" : "Next";
  next.addEventListener("click", nextTourStep);
  foot.appendChild(skip);
  foot.appendChild(next);
  b.appendChild(head);
  b.appendChild(p);
  if (step.demo) {
    const note = document.createElement("p");
    note.className = "tour-demo";
    note.textContent = step.demo;
    b.appendChild(note);
  }
  b.appendChild(dots);
  b.appendChild(foot);
  document.body.appendChild(b);
  next.focus();
}
function initTour() {
  const view = document.getElementById("view-dashboard");
  const settings = document.getElementById("widgetSettings");
  if (view && !document.getElementById("replayTourBtn")) {
    const btn = document.createElement("button");
    btn.id = "replayTourBtn";
    btn.type = "button";
    btn.textContent = "Replay tour";
    btn.addEventListener("click", startTour);
    if (settings && settings.nextSibling) settings.parentElement.insertBefore(btn, settings.nextSibling);
    else if (settings) settings.parentElement.appendChild(btn);
    else view.prepend(btn);
  }
  let seen = null;
  try { seen = localStorage.getItem(KUMON_TOUR_KEY); } catch (e) { seen = null; }
  if (!seen && view) setTimeout(startTour, 800);
}

// Accordion toggle for Employee Directory
function toggleAccordion(summaryElement) {
  const card = summaryElement.closest('.roster-accordion-card');
  const tag = summaryElement.querySelector('.acc-toggle-tag');
  
  if (card.classList.contains('open')) {
    card.classList.remove('open');
    card.querySelector('.acc-expanded-body')?.setAttribute('hidden', '');
    if (tag) {
      tag.innerHTML = `<svg class="chevron-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg> <span>Expand Profile</span>`;
    }
  } else {
    card.classList.add('open');
    card.querySelector('.acc-expanded-body')?.removeAttribute('hidden');
    if (tag) {
      tag.innerHTML = `<svg class="chevron-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"></polyline></svg> <span>Collapse Profile</span>`;
    }
  }
}


// Filter Employee Directory
function filterDirectory() {
  const dept = document.getElementById('deptFilter').value.toLowerCase();
  const role = document.getElementById('roleFilter').value.toLowerCase();
  const status = document.getElementById('statusFilter').value.toLowerCase();
  const query = (document.getElementById('empSearch')?.value || '').toLowerCase().trim();

  const cards = document.querySelectorAll('#employeeRosterList .roster-accordion-card');
  cards.forEach(card => {
    const cardDept = (card.getAttribute('data-dept') || '').toLowerCase();
    const cardRole = (card.getAttribute('data-role') || '').toLowerCase();
    const cardStatus = (card.getAttribute('data-status') || '').toLowerCase();

    const matchesDept = (dept === 'all' || cardDept === dept);
    const matchesRole = (role === 'all' || cardRole === role);
    const matchesStatus = (status === 'all' || cardStatus === status);
    const matchesQuery = (!query || (card.textContent || '').toLowerCase().includes(query));

    if (matchesDept && matchesRole && matchesStatus && matchesQuery) {
      card.style.display = 'block';
    } else {
      card.style.display = 'none';
    }
  });
}

// Promote vs Transfer vs Remove Employee mode switch
function setPtMode(mode) {
  const btnPromote = document.getElementById('btnModePromote');
  const btnTransfer = document.getElementById('btnModeTransfer');
  const btnRemove = document.getElementById('btnModeRemove');
  const title = document.getElementById('ptCardTitle');
  const subtitle = document.getElementById('ptCardSubtitle');
  const promoteContainer = document.getElementById('promoteFormContainer');
  const transferContainer = document.getElementById('transferFormContainer');
  const removeContainer = document.getElementById('removeFormContainer');

  if (btnPromote) btnPromote.classList.toggle('active', mode === 'promote');
  if (btnTransfer) btnTransfer.classList.toggle('active', mode === 'transfer');
  if (btnRemove) btnRemove.classList.toggle('active', mode === 'remove');

  if (mode === 'promote') {
    if (title) title.textContent = 'Promote Employee';
    if (subtitle) subtitle.textContent = 'Record the next role and pay-grade step with a clear effective date and promotion rationale.';
    if (promoteContainer) promoteContainer.style.display = 'block';
    if (transferContainer) transferContainer.style.display = 'none';
    if (removeContainer) removeContainer.style.display = 'none';
  } else if (mode === 'transfer') {
    if (title) title.textContent = 'Transfer employee';
    if (subtitle) subtitle.textContent = 'Move a person to a new team or work location and keep the effective date and rationale on the record.';
    if (promoteContainer) promoteContainer.style.display = 'none';
    if (transferContainer) transferContainer.style.display = 'block';
    if (removeContainer) removeContainer.style.display = 'none';
  } else if (mode === 'remove') {
    if (title) title.textContent = 'Employee Offboarding Processing Wizard';
    if (subtitle) subtitle.textContent = 'Complete the following exit procedures for the departing employee.';
    if (promoteContainer) promoteContainer.style.display = 'none';
    if (transferContainer) transferContainer.style.display = 'none';
    if (removeContainer) removeContainer.style.display = 'block';
  }
}

// Purge preview: always dry-run first, render server log. Real delete
// happens only via explicit confirm (double POST, never one click).
async function previewPurge(e) {
  if (e) e.preventDefault();
  const box = document.getElementById('purgePreviewBox');
  try {
    const res = await apiFetch('/api/purge-run/', {
      method: 'POST',
      body: JSON.stringify({ days: 30, dry_run: true }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.error === 'string' ? data.error : 'preview failed');
    const n = data.would_purge || 0;
    if (box) {
      box.style.display = 'block';
      box.textContent = n === 0
        ? 'Purge preview: nothing eligible (0 rows past 30 days).'
        : `Purge preview: ${n} row(s) eligible. Confirm deletes them + Supabase users.`;
    }
    showToast(`Purge preview: ${n} eligible.`);
  } catch (error) {
    showToast('Purge preview unavailable.', 'error');
  }
}

// Offboarding submit: exit docs (optional) ride the same 10MB + PDF/JPG/PNG
// guards as onboarding docs, then the DELETE (resign) runs as before.
document.querySelectorAll('[data-offboard-file]').forEach((input) => {
  input.addEventListener('change', () => {
    const label = input.closest('[data-offboard-doc]')?.querySelector('[data-offboard-label]');
    const name = input.files?.[0]?.name || 'Upload File';
    if (label) label.textContent = name;
  });
});

// Offboarding handler — resolves the employee by corporate email, then
// DELETEs via the existing soft-delete (resign) flow.
async function handleOffboardingSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const email = form.querySelector('input[type="email"]')?.value.trim() || '';
  // Exit docs ride validateOnboardingFile guards. Same rule, no new rule.
  for (const input of form.querySelectorAll('[data-offboard-file]')) {
    const err = input.files?.[0] ? validateOnboardingFile(input.files[0]) : null;
    if (err) {
      showToast(err, 'error');
      return;
    }
  }
  if (!email) {
    showToast('Corporate email is required to offboard.', 'error');
    return;
  }
  try {
    const listRes = await apiFetch('/api/employees/?page_size=50');
    if (!listRes.ok) throw new Error('lookup failed');
    const payload = await listRes.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    const match = rows.find((emp) => (emp.email || '').toLowerCase() === email.toLowerCase());
    if (!match) {
      showToast(`No employee found for ${email}.`, 'error');
      return;
    }
    const delRes = await apiFetch(`/api/employees/${match.id}/`, { method: 'DELETE' });
    if (!delRes.ok) throw new Error('offboard failed');
    const delData = await delRes.json().catch(() => ({}));
    if (delData.deauthed === false) {
      showToast('Offboarded, but chat/login revocation needs retry — purge will complete it.', 'error');
    } else {
      showToast('Offboarding finalized and exit clearance issued successfully!');
    }
    form.reset();
  } catch (error) {
    showToast('Offboarding could not be completed. Try again later.', 'error');
  }
}

// Onboarding modal open / close handlers
function openOnboardingModal() {
  const modal = document.getElementById('onboardingModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

function closeOnboardingModal() {
  const modal = document.getElementById('onboardingModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

// Global escape key listener for modals
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    closeOnboardingModal();
  }
});

// Onboarding compliance docs: label shows the picked file name; the files
// are POSTed as multipart to /api/onboarding-docs/ once the employee row
// exists (see handleOnboarding).
// Onboarding file guards (D33): mirror the backend 10MB + PDF/JPG/PNG rules
// so oversized or mistyped files are rejected before upload. Exit-doc and
// chat pickers reuse these same two constants, single source.
const ONBOARDING_MAX_BYTES = 10 * 1024 * 1024;
const ONBOARDING_ALLOWED_MIME = {
  'application/pdf': ['pdf'],
  'image/jpeg': ['jpg', 'jpeg'],
  'image/png': ['png'],
};

function validateOnboardingFile(file) {
  if (!file) return 'No file selected.';
  if (file.size > ONBOARDING_MAX_BYTES) {
    return `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum is 10MB.`;
  }
  const ext = String(file.name || '').split('.').pop().toLowerCase();
  const allowedExts = ONBOARDING_ALLOWED_MIME[file.type] || [];
  if (!allowedExts.includes(ext)) {
    return `Unsupported file type (${file.type || 'unknown'}). Allowed: PDF, JPG, PNG.`;
  }
  return null;
}

function handleDocFileSelected(input) {
  const file = input.files && input.files[0];
  const kind = input.dataset.docType;
  const label = input.closest('label')?.querySelector(`[data-doc-label="${kind}"]`);
  if (file) {
    const err = validateOnboardingFile(file);
    if (err) {
      input.value = '';
      if (label) label.textContent = 'Upload File';
      showToast(`${kind}: ${err}`, 'error');
      return;
    }
  }
  if (label) label.textContent = file ? file.name : 'Upload File';
  if (file) showToast(`${file.name} attached for ${kind}.`);
}

async function uploadOnboardingDocs(form, employeeId) {
  const inputs = form.querySelectorAll('input[type="file"][data-doc-type]');
  let saved = 0;
  for (const input of inputs) {
    const file = input.files && input.files[0];
    if (!file) continue;
    const docType = input.dataset.docType;
    const invalid = validateOnboardingFile(file);
    if (invalid) {
      showToast(`${docType}: ${invalid}`, 'error');
      continue;
    }
    const docData = new FormData();
    docData.append('employee', employeeId);
    docData.append('doc_type', docType);
    docData.append('file', file);
    try {
      const res = await apiFetch('/api/onboarding-docs/', {
        method: 'POST',
        body: docData,
      });
      if (!res.ok) throw new Error('upload failed');
      saved += 1;
    } catch (error) {
      showToast(`${docType} upload failed — employee created, retry from directory.`, 'error');
    }
  }
  return saved;
}

// Onboarding form submit handler: POST the wizard fields to the live API,
// then upload any attached compliance docs against the new employee row.
async function handleOnboarding(e) {
  e.preventDefault();
  const form = e.target;
  const fullName = (form.querySelector('input[type="text"]')?.value || '').trim();
  const email = (form.querySelector('input[type="email"]')?.value || '').trim();
  const parts = fullName.split(/\s+/).filter(Boolean);
  const payload = {
    first_name: parts[0] || '',
    last_name: parts.slice(1).join(' ') || '',
    email,
  };
  const deptName = (form.querySelector('#onboardDepartment')?.value || '').trim();
  const roleVal = (form.querySelector('#onboardRole')?.value || '').trim();
  if (roleVal) payload.role = roleVal.split('•')[0].trim();
  if (deptName) {
    const depots = await apiFetch('/api/departments/').then((r) => r.json()).catch(() => []);
    const rows = Array.isArray(depots) ? depots : depots.results || [];
    const hit = rows.find((d) => (d.name || '').toLowerCase() === deptName.toLowerCase());
    if (hit) payload.department = hit.id;
  }
  apiFetch('/api/employees/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err =
          typeof data.error === 'string'
            ? data.error
            : 'Unable to create employee. Check the form and try again.';
        showToast(err);
        return null;
      }
      return data;
    })
    .then((data) => {
      if (!data) return;
      const finish = (docCount) => {
        const suffix = docCount ? ` (${docCount} compliance doc${docCount > 1 ? 's' : ''} saved)` : '';
        showToast(`Employee ${fullName || email} created & credentials issued!${suffix}`);
        closeOnboardingModal();
        form.reset();
        form.querySelectorAll('[data-doc-label]').forEach((el) => { el.textContent = 'Upload File'; });
        loadEmployeeDirectory();
      };
      if (data.id) {
        uploadOnboardingDocs(form, data.id).then(finish);
      } else {
        // Anonymous signup returns 202 with no row id: docs stay attached
        // to the form until the directory record exists.
        showToast('Signup received — compliance docs upload after HR confirms the profile.');
        finish(0);
      }
    })
    .catch(() => showToast('Unable to create employee upstream. Try again later.', 'error'));
}

// Grievance handler (D36): files the record to POST /api/messages/ under the
// frozen grievance conversation key; the demo case list stays untouched.
async function handleGrievanceSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const complainant = document.getElementById('grievComplainant')?.value || 'Anonymous Filing';
  const category = document.getElementById('grievCategory')?.value || 'Workplace Environment / Workload';
  const title = document.getElementById('grievTitle')?.value.trim() || '';
  const details = document.getElementById('grievDetails')?.value.trim() || '';
  const text = `[${category}] ${title} — ${details} (Complainant: ${complainant})`;
  try {
    const res = await apiFetch('/api/messages/', {
      method: 'POST',
      body: JSON.stringify({ conversation_key: 'grievance', text }),
    });
    if (!res.ok) throw new Error('file failed');
    showToast('Confidential grievance filed and assigned to HR Mediator.');
    form.reset();
  } catch (err) {
    showToast('Grievance could not be filed. Try again later.', 'error');
  }
}

// ==========================================================================
// Shift Management Handlers
// ==========================================================================
function toggleShiftCalendar() {
  const cal = document.getElementById('shiftCalendarContainer');
  const txt = document.getElementById('shiftCalToggleText');
  if (!cal) return;

  if (cal.classList.contains('collapsed')) {
    cal.classList.remove('collapsed');
    if (txt) txt.textContent = 'Collapse Calendar';
    showToast('Shift Roster Master Calendar expanded.');
  } else {
    cal.classList.add('collapsed');
    if (txt) txt.textContent = 'Expand Calendar';
    showToast('Shift Roster Master Calendar collapsed.');
  }
}


// ==========================================================================
// Integrated Shift Management Handlers
// ==========================================================================

function formatShiftDisplayDate(dateObj) {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const dayName = days[dateObj.getDay()];
  const dayNum = dateObj.getDate();
  const monthName = months[dateObj.getMonth()];
  const year = dateObj.getFullYear();
  return `${dayName}, ${dayNum} ${monthName} ${year}`;
}

function handleShiftDateChange(dateVal) {
  if (!dateVal) return;
  const parts = dateVal.split('-');
  if (parts.length === 3) {
    const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    const label = formatShiftDisplayDate(d);
    const displayEl = document.getElementById('shiftDateDisplay');
    if (displayEl) {
      displayEl.textContent = `Allocation (demo) for ${label}`;
    }
    showToast(`Roster updated for ${label}`);
  }
}

function stepShiftDate(offsetDays) {
  const picker = document.getElementById('shiftDatePicker');
  if (!picker) return;
  let currentDate = picker.value ? new Date(picker.value) : new Date(2026, 5, 18);
  if (isNaN(currentDate.getTime())) {
    currentDate = new Date(2026, 5, 18);
  }
  currentDate.setDate(currentDate.getDate() + offsetDays);
  const yyyy = currentDate.getFullYear();
  const mm = String(currentDate.getMonth() + 1).padStart(2, '0');
  const dd = String(currentDate.getDate()).padStart(2, '0');
  const newDateStr = `${yyyy}-${mm}-${dd}`;
  picker.value = newDateStr;
  handleShiftDateChange(newDateStr);
}

function setShiftDateToday() {
  const picker = document.getElementById('shiftDatePicker');
  if (!picker) return;
  const todayStr = '2026-06-18'; // Demo live date
  picker.value = todayStr;
  handleShiftDateChange(todayStr);
  showToast('Reset roster view to Today (18 June 2026).');
}

// Live employee id lookup shared by the advance + roster forms: the
// directory loaded at startup first, then a fresh /api/employees/ fetch.
async function resolveEmployeeId(name) {
  const key = String(name || '').trim().toLowerCase();
  if (!key) return null;
  if (employeeNameIndex[key]) return employeeNameIndex[key];
  try {
    const res = await apiFetch('/api/employees/?page_size=100');
    if (!res.ok) return null;
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    rows.forEach((e) => {
      const full = `${e.first_name || ''} ${e.last_name || ''}`.trim().toLowerCase();
      if (full) employeeNameIndex[full] = e.id;
      if (e.email) employeeNameIndex[String(e.email).toLowerCase()] = e.id;
    });
  } catch (_) { /* directory unreachable */ }
  return employeeNameIndex[key] || null;
}

function toggleAddStaffForm(shiftKey, show) {
  const form = document.getElementById(`addStaffForm-${shiftKey}`);
  const addBtn = document.getElementById(`btnAddStaff-${shiftKey}`);
  if (!form) return;

  if (show === undefined) {
    show = form.style.display === 'none' || form.style.display === '';
  }

  if (show) {
    form.style.display = 'block';
    if (addBtn) addBtn.style.display = 'none';
    const select = document.getElementById(`staffSelect-${shiftKey}`);
    if (select) select.focus();
  } else {
    form.style.display = 'none';
    if (addBtn) addBtn.style.display = 'block';
  }
}

function confirmAddStaff(shiftKey) {
  const select = document.getElementById(`staffSelect-${shiftKey}`);
  const roleSelect = document.getElementById(`roleSelect-${shiftKey}`);
  const usersList = document.getElementById(`shiftUsers-${shiftKey}`);
  const shiftBadge = document.getElementById(`shiftBadge-${shiftKey}`);

  if (!select || !select.value) {
    showToast('Please choose an employee to assign.');
    if (select) select.focus();
    return;
  }

  const [name, jobTitle, initials] = select.value.split('|');
  const roleTag = roleSelect ? roleSelect.value : 'Duty Staff';

  // Remove empty placeholder if present
  const placeholder = usersList.querySelector('.shift-empty-placeholder');
  if (placeholder) placeholder.remove();

  // Create new user row
  const userRow = document.createElement('div');
  userRow.className = 'shift-slot-user-row';
  userRow.innerHTML = `
    <div class="shift-slot-user-left">
      <div class="shift-staff-avatar" style="width:28px; height:28px; font-size:11px;">${escapeHtml(initials)}</div>
      <div>
        <strong style="font-size:13px; color:#0f172a;">${escapeHtml(name)}</strong>
        <div style="font-size:11px; color:#64748b;">${escapeHtml(jobTitle)} &bull; ${escapeHtml(roleTag)}</div>
      </div>
    </div>
    <button class="btn-remove-staff" title="Remove staff" onclick="removeShiftStaff(this)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
  `;

  usersList.appendChild(userRow);

  // Update shift card badge
  if (shiftBadge) {
    shiftBadge.className = 'penpot-badge badge-present';
    shiftBadge.style.fontSize = '11px';
    shiftBadge.textContent = 'Draft';
  }

  // Reset and hide form
  select.selectedIndex = 0;
  if (roleSelect) roleSelect.selectedIndex = 0;
  toggleAddStaffForm(shiftKey, false);

  updateShiftCoverageStatus();
  persistShiftAssignment(shiftKey, name).then((saved) => {
    showToast(
      saved
        ? `Assigned ${name} (${roleTag}) successfully!`
        : 'Assigned locally — roster save needs retry.',
      saved ? undefined : 'error'
    );
  });
}

// Roster persistence (D36): mirrors the slot assignment into
// POST /api/shift-rosters/ for the date picked in the roster editor,
// keeping the optimistic card row when the API is unreachable.
const SHIFT_SLOT_TIMES = {
  morning: ['08:00:00', '16:00:00'],
  evening: ['16:00:00', '23:00:00'],
  night: ['00:00:00', '08:00:00'],
};

async function persistShiftAssignment(shiftKey, name) {
  try {
    const employeeId = await resolveEmployeeId(name);
    if (!employeeId) return false;
    const workDate = document.getElementById('shiftDatePicker')?.value || null;
    const times = SHIFT_SLOT_TIMES[shiftKey] || SHIFT_SLOT_TIMES.morning;
    const res = await apiFetch('/api/shift-rosters/', {
      method: 'POST',
      body: JSON.stringify({
        employee: employeeId,
        work_date: workDate,
        shift_type: shiftKey,
        start_time: times[0],
        end_time: times[1],
      }),
    });
    if (res.ok && typeof loadShiftRosterView === 'function') loadShiftRosterView();
    return res.ok;
  } catch (_) {
    return false;
  }
}

function focusRosterEditor() {
  const editor = document.getElementById('shiftSlotsContainer');
  if (editor && editor.scrollIntoView) editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
  toggleAddStaffForm('morning', true);
  showToast('Roster editor ready — pick a slot and assign staff.');
}

function removeShiftStaff(btn) {
  const userRow = btn.closest('.shift-slot-user-row');
  const usersList = userRow?.closest('.shift-slot-users-list');
  const slotCard = userRow?.closest('.shift-slot-card');

  if (userRow) {
    userRow.style.opacity = '0';
    userRow.style.transform = 'scale(0.95)';
    userRow.style.transition = 'all 0.2s ease';
    setTimeout(() => {
      userRow.remove();

      if (usersList && usersList.querySelectorAll('.shift-slot-user-row').length === 0) {
        usersList.innerHTML = `<div class="shift-empty-placeholder">No staff currently assigned</div>`;
        const badge = slotCard?.querySelector('.shift-slot-card-head .penpot-badge');
        if (badge) {
          badge.className = 'penpot-badge badge-absent';
          badge.textContent = 'Uncovered';
        }
      }

      updateShiftCoverageStatus();
      showToast('Employee removed from shift slot.');
    }, 200);
  }
}

function updateShiftCoverageStatus() {
  const slots = ['morning', 'evening', 'night'];
  let coveredCount = 0;

  slots.forEach(s => {
    const list = document.getElementById(`shiftUsers-${s}`);
    if (list && list.querySelectorAll('.shift-slot-user-row').length > 0) {
      coveredCount++;
    }
  });

  const overallBadge = document.getElementById('shiftOverallCoverage');
  if (overallBadge) {
    const pct = Math.round((coveredCount / slots.length) * 100);
    overallBadge.textContent = `● ${pct}% Covered`;
    if (pct === 100) {
      overallBadge.className = 'penpot-badge badge-present';
    } else if (pct >= 50) {
      overallBadge.className = 'penpot-badge badge-late';
    } else {
      overallBadge.className = 'penpot-badge badge-absent';
    }
  }
}

// ==========================================================================
// Claims & Reimbursements Handlers
// ==========================================================================
function showToast(message, type) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
  if (type === 'error') toast.style.borderLeft = '4px solid #dc2626';
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function switchClaimsTab(tabKey) {
  // Update tabs
  document.getElementById('claimsTabBtnPending')?.classList.toggle('active', tabKey === 'pending');
  document.getElementById('claimsTabBtnHistory')?.classList.toggle('active', tabKey === 'history');
  document.getElementById('claimsTabBtnAdvance')?.classList.toggle('active', tabKey === 'advance');

  // Update panels
  const pnlPending = document.getElementById('claimsSubpanelPending');
  const pnlHistory = document.getElementById('claimsSubpanelHistory');
  const pnlAdvance = document.getElementById('claimsSubpanelAdvance');

  if (pnlPending) pnlPending.style.display = (tabKey === 'pending' ? 'block' : 'none');
  if (pnlHistory) pnlHistory.style.display = (tabKey === 'history' ? 'block' : 'none');
  if (pnlAdvance) pnlAdvance.style.display = (tabKey === 'advance' ? 'block' : 'none');
}

function filterClaimsTable(input, tableBodyId) {
  const q = input.value.toLowerCase();
  const rows = document.querySelectorAll(`#${tableBodyId} tr`);
  rows.forEach(r => {
    const text = r.textContent.toLowerCase();
    r.style.display = text.includes(q) ? '' : 'none';
  });
}

function renderClaimStatus(id, status) {
  const statusElem = document.getElementById(`status-${id}`);
  const actionsElem = document.getElementById(`actions-${id}`);

  if (!statusElem) return;

  statusElem.className = `claims-status-pill ${status.toLowerCase()}`;
  statusElem.textContent = status;
  if (actionsElem) {
    actionsElem.innerHTML = `<span style="font-size:12px; color:#64748b; font-weight:600;">Processed</span>`;
  }
}

async function loadClaimStatuses() {
  try {
    const response = await apiFetch('/api/claim-statuses/', { cache: 'no-store' });
    if (!response.ok) throw new Error('Unable to load claim statuses.');
    const payload = await response.json();
    const statuses = Array.isArray(payload) ? payload : payload.results || [];
    statuses.forEach(({ claim_id, status }) => renderClaimStatus(claim_id, status));
  } catch (error) {
    showToast('Claim statuses could not be loaded.');
  }
}

async function saveClaimStatus(id, status) {
  // Claim decisions go through POST /api/claims/<id>/decision/ (UUID rows
  // and demo CLM-/ADV- codes alike); the legacy claim-statuses upsert stays
  // as the offline-shaped fallback.
  const decision = status === 'Approved' ? 'Approved' : 'Rejected';
  const res = await apiFetch(`/api/claims/${encodeURIComponent(id)}/decision/`, {
    method: 'POST',
    body: JSON.stringify({ decision })
  });
  if (res.ok) return;
  const legacy = await apiFetch('/api/claim-statuses/', {
    method: 'POST',
    body: JSON.stringify({ claim_id: id, status: decision })
  });
  if (!legacy.ok) throw new Error('Unable to save claim status.');
}

async function handleClaimAction(id, action) {
  const status = action === 'Approve' ? 'Approved' : 'Rejected';
  try {
    await saveClaimStatus(id, status);
    renderClaimStatus(id, status);
  } catch (error) {
    showToast('Claim status could not be saved.');
    return;
  }

  const message = status === 'Approved'
    ? `Claim ${id} approved for reimbursement settlement.`
    : `Claim ${id} flagged and marked as rejected.`;
  showToast(message);
  if (typeof updateBatchApproveCount === 'function') updateBatchApproveCount();
}

async function batchApproveClaims() {
  const pendingBadges = document.querySelectorAll('#pendingClaimsTableBody .claims-status-pill.pending');
  let approved = 0;
  for (const b of pendingBadges) {
    const id = b.id.replace('status-', '');
    try {
      await saveClaimStatus(id, 'Approved');
      renderClaimStatus(id, 'Approved');
      approved += 1;
    } catch (error) {
      showToast('Claim status could not be saved.');
      return;
    }
  }
  updateBatchApproveCount();
  showToast(
    approved
      ? `Batch approved ${approved} pending expense claim${approved > 1 ? 's' : ''}.`
      : 'No pending expense claims to batch approve.'
  );
}

// Live batch count (D36): the Batch Approve button always shows the live
// number of pending rows currently in the pending register.
function updateBatchApproveCount() {
  const count = document.querySelectorAll('#pendingClaimsTableBody .claims-status-pill.pending').length;
  document.querySelectorAll('[data-batch-approve-count]').forEach((btn) => {
    btn.textContent = `+ Batch Approve (${count})`;
  });
}

// ==========================================================================
// Live pagers (D34): every pager button fetches its list with ?page=N and
// renders the live rows, keeping the static demo markup as offline fallback.
// ==========================================================================
const claimsPagerState = { pending: 1, history: 1 };
const CLAIMS_PAGE_SIZE = 6;

function claimsPagerStep(which, delta) {
  claimsPagerGoto(which, (claimsPagerState[which] || 1) + delta);
}

function markPagerActive(pagerName, page) {
  const bar = document.querySelector(`[data-pager="${pagerName}"]`);
  if (!bar) return;
  bar.dataset.page = String(page);
  bar.querySelectorAll('[data-pagenum]').forEach((btn) => {
    btn.classList.toggle('active', Number(btn.dataset.pagenum) === page);
  });
}

function claimInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '—';
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

function fmtClaimDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? '—' : d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

async function claimsPagerGoto(which, page) {
  if (page < 1) return;
  const bodyId = which === 'pending' ? 'pendingClaimsTableBody' : 'historyClaimsTableBody';
  const infoId = which === 'pending' ? 'pendingPagerInfo' : 'historyPagerInfo';
  const pagerName = which === 'pending' ? 'claims-pending' : 'claims-history';
  const body = document.getElementById(bodyId);
  if (!body) return;
  const demo = body.dataset.demoHtml || body.innerHTML;
  body.dataset.demoHtml = demo;
  try {
    const res = await apiFetch(`/api/expense-claims/?page=${page}&page_size=${CLAIMS_PAGE_SIZE}`);
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    const total = typeof payload.count === 'number' ? payload.count : rows.length;
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to ids */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7">No expense claims on this page yet.</td></tr>';
    } else {
      rows.forEach((c) => body.appendChild(buildClaimRow(c, which, names)));
    }
    const info = document.getElementById(infoId);
    if (info) info.textContent = `Showing page ${page} of ${total} live expense claims`;
    claimsPagerState[which] = page;
    markPagerActive(pagerName, page);
    setApiMode('live');
    if (which === 'pending' && typeof updateBatchApproveCount === 'function') updateBatchApproveCount();
  } catch (e) {
    body.innerHTML = demo;
    showToast('Claims page unreachable — showing demo data', 'error');
  }
}

function buildClaimRow(c, which, names) {
  const id = String(c.id || '');
  const who = String(names[c.employee] || c.employee || 'Unknown');
  const statusCls = String(c.status || 'Pending').toLowerCase();
  const tr = document.createElement('tr');
  tr.id = `claim-row-${id}`;
  tr.setAttribute('data-live', 'true');
  const pill = `<span class="claims-status-pill ${statusCls}" id="status-${id}">${escapeHtml(String(c.status || 'Pending'))}</span>`;
  const actions =
    `<div class="claims-actions-cell" id="actions-${id}">` +
    `<button class="btn-claim-approve" onclick="handleClaimAction('${escapeHtml(id)}', 'Approve')">Approve</button>` +
    `<button class="btn-claim-reject" onclick="handleClaimAction('${escapeHtml(id)}', 'Reject')">Reject</button>` +
    `</div>`;
  if (which === 'history') {
    tr.innerHTML =
      `<td><div class="claims-applicant-cell"><div class="claims-avatar">${escapeHtml(claimInitials(who))}</div>` +
      `<div class="claims-applicant-info"><strong>${escapeHtml(who)} &nbsp;<span style="color:#64748b; font-weight:500;">[${escapeHtml(id.slice(0, 12))}]</span></strong>` +
      `<span>${escapeHtml(String(c.category || ''))}</span></div></div></td>` +
      `<td><span class="claims-cat-pill">${escapeHtml(String(c.category || 'General Expense'))}</span></td>` +
      `<td>${escapeHtml(fmtClaimDate(c.created_at))}</td>` +
      `<td>${escapeHtml(String(c.title || ''))}</td>` +
      `<td><span class="claims-amount-txt">$${escapeHtml(Number(c.amount || 0).toFixed(2))}</span></td>` +
      `<td>${pill}</td><td>—</td>`;
  } else {
    tr.innerHTML =
      `<td><div class="claims-applicant-cell"><div class="claims-avatar">${escapeHtml(claimInitials(who))}</div>` +
      `<div class="claims-applicant-info"><strong>${escapeHtml(who)} &nbsp;<span style="color:#64748b; font-weight:500;">[${escapeHtml(id.slice(0, 12))}]</span></strong>` +
      `<span>${escapeHtml(String(c.category || ''))}</span></div></div></td>` +
      `<td><span class="claims-cat-pill">${escapeHtml(String(c.category || 'General Expense'))}</span></td>` +
      `<td>${escapeHtml(fmtClaimDate(c.created_at))}</td>` +
      `<td><div class="claims-details-cell"><div class="claims-details-text">${escapeHtml(String(c.title || ''))}</div></div></td>` +
      `<td><span class="claims-amount-txt">$${escapeHtml(Number(c.amount || 0).toFixed(2))}</span></td>` +
      `<td>${pill}</td><td>${actions}</td>`;
  }
  return tr;
}

// Advances pager (D34): ?page=N against /api/advances/, same register row
// shape as the static demo markup, which stays as the offline fallback.
let advancesPagerPage = 1;
const ADVANCES_PAGE_SIZE = 4;

function advancesPagerStep(delta) {
  advancesPagerGoto(advancesPagerPage + delta);
}

function buildAdvanceRow(a, names) {
  const id = String(a.id || '');
  const who = String(names[a.employee] || a.employee || 'Unknown');
  const statusCls = String(a.status || 'Pending').toLowerCase();
  const tr = document.createElement('tr');
  tr.id = `adv-row-${id}`;
  tr.setAttribute('data-live', 'true');
  const pill = `<span class="claims-status-pill ${statusCls}" id="status-${id}">${escapeHtml(String(a.status || 'Pending'))}</span>`;
  const actions =
    `<div class="claims-actions-cell" id="actions-${id}">` +
    `<button class="btn-claim-approve" onclick="handleClaimAction('${escapeHtml(id)}', 'Approve')">Approve</button>` +
    `<button class="btn-claim-reject" onclick="handleClaimAction('${escapeHtml(id)}', 'Reject')">Reject</button>` +
    `</div>`;
  tr.innerHTML =
    `<td><div class="claims-applicant-cell"><div class="claims-avatar">${escapeHtml(claimInitials(who))}</div>` +
    `<div class="claims-applicant-info"><strong>${escapeHtml(who)} &nbsp;<span style="color:#64748b; font-weight:500;">[${escapeHtml(id.slice(0, 12))}]</span></strong>` +
    `<span>Advance request</span></div></div></td>` +
    `<td><span class="claims-amount-txt">$${escapeHtml(Number(a.amount || 0).toFixed(2))}</span></td>` +
    `<td><span class="claims-cat-pill">${escapeHtml(String(a.repayment_terms || 'Next Payroll'))}</span></td>` +
    `<td>${escapeHtml(String(a.purpose || ''))}</td>` +
    `<td>—</td>` +
    `<td>${pill}</td><td>${actions}</td>`;
  return tr;
}

async function advancesPagerGoto(page) {
  if (page < 1) return;
  const body = document.getElementById('advanceClaimsTableBody');
  if (!body) return;
  const demo = body.dataset.demoHtml || body.innerHTML;
  body.dataset.demoHtml = demo;
  try {
    const res = await apiFetch(`/api/advances/?page=${page}&page_size=${ADVANCES_PAGE_SIZE}`);
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    const total = typeof payload.count === 'number' ? payload.count : rows.length;
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to ids */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7">No advance applications on this page yet.</td></tr>';
    } else {
      rows.forEach((a) => body.appendChild(buildAdvanceRow(a, names)));
    }
    const info = document.getElementById('advancesPagerInfo');
    if (info) info.textContent = `Showing page ${page} of ${total} live advance pay applications`;
    advancesPagerPage = page;
    markPagerActive('advances', page);
    setApiMode('live');
  } catch (e) {
    body.innerHTML = demo;
    showToast('Advances page unreachable — showing demo data', 'error');
  }
}


// Advance Pay Modal
function openAdvanceModal() {
  const modal = document.getElementById('advanceModal');
  if (modal) modal.classList.add('active');
}

function closeAdvanceModal() {
  const modal = document.getElementById('advanceModal');
  if (modal) modal.classList.remove('active');
}

// Live advances register (D36): replaces the static demo tbody with live
// /api/advances/ rows, keeping the demo markup as the offline fallback.
async function loadAdvancesView() {
  const body = document.getElementById('advanceClaimsTableBody');
  if (!body) return;
  const demo = body.dataset.demoHtml || body.innerHTML;
  body.dataset.demoHtml = demo;
  try {
    const res = await apiFetch('/api/advances/?page_size=50');
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to ids */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7">No advance applications yet.</td></tr>';
    } else {
      rows.forEach((a) => body.appendChild(buildAdvanceRow(a, names)));
    }
    setApiMode('live');
  } catch (e) { body.innerHTML = demo; setApiMode('demo'); showToast('Advances unreachable — showing demo data', 'error'); }
}

async function handleRequestAdvance(e) {
  e.preventDefault();
  const form = e.target;
  const applicantRaw = document.getElementById('advanceApplicant')?.value || '';
  const applicantName = applicantRaw.replace(/\s*\(.*\)\s*/, '').trim();
  const amount = document.getElementById('advanceAmount')?.value || '';
  const terms = document.getElementById('advanceTerms')?.value || 'Next Payroll';
  const purpose = document.getElementById('advancePurpose')?.value.trim() || '';
  if (!(Number(amount) > 0)) {
    showToast('Requested amount must be greater than zero.', 'error');
    return;
  }
  const employeeId = await resolveEmployeeId(applicantName);
  if (!employeeId) {
    showToast('Applicant is not in the live employee directory yet.');
    return;
  }
  try {
    const res = await apiFetch('/api/advances/', {
      method: 'POST',
      body: JSON.stringify({
        employee: employeeId,
        amount,
        repayment_terms: terms,
        purpose,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const err =
        typeof data.error === 'string'
          ? data.error
          : typeof data.detail === 'string'
            ? data.detail
            : 'Unable to submit advance request. Check the amount and try again.';
      showToast(err, 'error');
      return;
    }
    closeAdvanceModal();
    showToast('Salary advance application submitted for HR cap verification.');
    form.reset();
    loadAdvancesView();
  } catch (err) {
    showToast('Unable to submit advance request. Try again later.', 'error');
  }
}

// Leave Application Modal
function openLeaveModal() {
  const modal = document.getElementById('leaveModal');
  if (modal) modal.classList.add('active');
}

function closeLeaveModal() {
  const modal = document.getElementById('leaveModal');
  if (modal) modal.classList.remove('active');
}

function handleApplyLeave(e) {
  e.preventDefault();
  const form = e.target;
  const selects = form.querySelectorAll('select');
  const dates = form.querySelectorAll('input[type="date"]');
  const reason = form.querySelector('textarea')?.value || '';
  const applicantName = (selects[0]?.value || '')
    .replace(/\s*\(.*\)\s*/, '')
    .trim()
    .toLowerCase();
  const employeeId = employeeNameIndex[applicantName];
  if (!employeeId) {
    showToast('Applicant is not in the live employee directory yet.');
    return;
  }
  apiFetch('/api/leaves/', {
    method: 'POST',
    body: JSON.stringify({
      employee: employeeId,
      leave_type: selects[1]?.value || 'Personal',
      start_date: dates[0]?.value || null,
      end_date: dates[1]?.value || null,
      reason,
    }),
  })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err =
          typeof data.error === 'string'
            ? data.error
            : 'Unable to file leave. Check the dates and try again.';
        showToast(err);
        return null;
      }
      return data;
    })
    .then((data) => {
      if (!data) return;
      closeLeaveModal();
      showToast('Leave request submitted for HR approval.');
      form.reset();
    })
    .catch(() => showToast('Unable to file leave. Try again later.', 'error'));
}


// ==========================================================================
// Messages & Channels Handlers
// ==========================================================================
let activeConversationKey = 'sarah';
let messagesLoadVersion = 0;
let mentionInputCursor = 0;

function toggleMentionPicker(event) {
  event.stopPropagation();
  const picker = document.getElementById('mentionPicker');
  const input = document.getElementById('chatTextInput');
  if (!picker || !input) return;

  mentionInputCursor = input.selectionStart ?? input.value.length;
  picker.hidden = !picker.hidden;
}

function insertMention(name) {
  const picker = document.getElementById('mentionPicker');
  const input = document.getElementById('chatTextInput');
  if (!input) return;

  const mention = `@${name}`;
  const cursor = mentionInputCursor || input.value.length;
  input.value = `${input.value.slice(0, cursor)}${mention} ${input.value.slice(cursor)}`;
  input.focus();
  input.setSelectionRange(cursor + mention.length + 1, cursor + mention.length + 1);
  if (picker) picker.hidden = true;
}

document.addEventListener('click', event => {
  const picker = document.getElementById('mentionPicker');
  if (picker && !picker.contains(event.target) && !event.target.closest('.composer-tool-btn')) {
    picker.hidden = true;
  }
});

function filterInboxes(input) {
  const q = input.value.toLowerCase();
  const tiles = document.querySelectorAll('#inboxConversationsList .inbox-user-tile');
  tiles.forEach(tile => {
    const text = tile.textContent.toLowerCase();
    tile.style.display = text.includes(q) ? 'flex' : 'none';
  });
}

function selectChannel(elem, channelKey) {
  activeConversationKey = channelKey;
  document.querySelectorAll('.channel-list-item, .inbox-user-tile').forEach(el => el.classList.remove('active'));
  elem.classList.add('active');

  const avatar = document.getElementById('activeChatAvatar');
  const name = document.getElementById('activeChatName');
  const status = document.getElementById('activeChatStatus');
  const input = document.getElementById('chatTextInput');

  if (avatar) {
    avatar.className = 'avatar-circle-md avatar-slate';
    avatar.textContent = '#';
  }
  if (name) name.textContent = 'Company Announcements';
  if (status) status.textContent = '● Broadcast Channel • All Staff';
  if (input) input.placeholder = 'Post an announcement to the team...';
  loadMessagesForConversation(channelKey);
  showToast('Switched to # Company Announcements channel.');
}

// Slack is not integrated: route profile "Message on Slack" into the chat tab.
function messageOnSlack(fullName) {
  switchView('messages');
  const tiles = document.querySelectorAll('.inbox-user-tile');
  const hit = Array.from(tiles).find((t) =>
    (t.textContent || '').toLowerCase().includes((fullName || '').toLowerCase().split(' ')[0])
  );
  if (hit) hit.click();
  else showToast('Slack is not connected — continue here in the chat tab.');
}
function selectInboxUser(elem, userName, initials, userRole, key) {
  activeConversationKey = key;
  document.querySelectorAll('.channel-list-item, .inbox-user-tile').forEach(el => el.classList.remove('active'));
  elem.classList.add('active');
  elem.classList.remove('unread');
  const unreadBadge = elem.querySelector('.unread-count-pill');
  if (unreadBadge) unreadBadge.remove();

  const avatar = document.getElementById('activeChatAvatar');
  const name = document.getElementById('activeChatName');
  const status = document.getElementById('activeChatStatus');
  const input = document.getElementById('chatTextInput');

  if (avatar) {
    avatar.className = `avatar-circle-md avatar-blue`;
    avatar.textContent = initials;
  }
  if (name) name.textContent = userName;
  if (status) status.textContent = `● ${userRole} • Online Now`;
  if (input) input.placeholder = `Type a message to ${userName}...`;
  loadMessagesForConversation(key);
  showToast(`Active chat: ${userName}`);
}

async function loadMessagesForConversation(conversationKey) {
  const stream = document.getElementById('chatStreamMessages');
  if (!stream) return;

  const loadVersion = ++messagesLoadVersion;
  document.querySelectorAll('[data-persisted-message="true"]').forEach(message => message.remove());
  try {
    const response = await apiFetch(`/api/messages/?conversation=${encodeURIComponent(conversationKey)}`, {
      cache: 'no-store'
    });
    if (!response.ok) throw new Error('Unable to load messages.');
    const payload = await response.json();
    const messages = Array.isArray(payload) ? payload : payload.results || [];
    if (loadVersion !== messagesLoadVersion) return;
    messages.forEach(message => appendPersistedMessage(stream, message));
    stream.scrollTop = stream.scrollHeight;
  } catch (error) {
    showToast('Messages could not be loaded.');
  }
}

function appendPersistedMessage(stream, message) {
  const row = document.createElement('div');
  row.className = 'chat-msg-row outgoing';
  row.dataset.persistedMessage = 'true';

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble outgoing';
  if (message.text) {
    const text = document.createElement('p');
    text.textContent = message.text;
    bubble.appendChild(text);
  }
  if (message.attachment_url) {
    const link = document.createElement('a');
    link.href = message.attachment_url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = `Attachment: ${message.attachment_url.split('/').pop()}`;
    bubble.appendChild(link);
  }
  const timestamp = document.createElement('span');
  timestamp.className = 'chat-time-stamp outgoing-stamp';
  timestamp.textContent = `${new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Sent`;
  bubble.appendChild(timestamp);
  row.appendChild(bubble);
  stream.appendChild(row);
}

function handleChatFileSelected(input) {
  const file = input.files[0];
  if (!file) return;
  // Same 10MB + PDF/JPG/PNG rule as onboarding docs, single source.
  const err = validateOnboardingFile(file);
  if (err) {
    showToast(err, 'error');
    input.value = '';
    return;
  }
  showToast(`${file.name} attached. Add a message or press Send Message.`);
}

async function handleSendChatMessage(e) {
  e.preventDefault();
  const input = document.getElementById('chatTextInput');
  const text = input.value.trim();
  const fileInput = document.getElementById('chatFileInput');
  const imageInput = document.getElementById('chatImageInput');
  const file = fileInput.files[0] || imageInput.files[0];
  if (!text && !file) return;
  messagesLoadVersion += 1;

  const formData = new FormData();
  formData.append('conversation_key', activeConversationKey);
  formData.append('sender_name', 'Marcus Williams');
  formData.append('text', text);
  if (file) formData.append('attachment', file);

  let savedMessage;
  try {
    const response = await apiFetch('/api/messages/', { method: 'POST', body: formData });
    if (!response.ok) throw new Error('Unable to save message.');
    savedMessage = await response.json();
  } catch (error) {
    showToast('Message could not be saved.');
    return;
  }

  const stream = document.getElementById('chatStreamMessages');
  if (stream && savedMessage) {
    appendPersistedMessage(stream, savedMessage);
    stream.scrollTop = stream.scrollHeight;
  }

  input.value = '';
  fileInput.value = '';
  imageInput.value = '';
  showToast('Message sent.');
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ==========================================================================
// Standalone Authentication Handlers & Navigation
// ==========================================================================
function switchAuthPage(mode = 'login') {
  const loginCard = document.getElementById('authScreenLogin');
  const signupCard = document.getElementById('authScreenSignup');

  if (loginCard && signupCard) {
    if (mode === 'signup') {
      loginCard.style.display = 'none';
      signupCard.style.display = 'block';
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', '#signup');
      }
      document.title = 'Employee Registration • Kumon EMS';
    } else {
      signupCard.style.display = 'none';
      loginCard.style.display = 'block';
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', '#login');
      }
      document.title = 'Employee Login • Kumon EMS';
    }
  }
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = 'Hide';
  } else {
    input.type = 'password';
    btn.textContent = 'Show';
  }
}

function handleAuthLogin(e) {
  if (e) e.preventDefault();
  const username = (document.getElementById('loginEmployeeId')?.value || '').trim();
  const password = document.getElementById('loginPasswordInput')?.value || '';
  // Real session login — deliberately NOT via apiFetch: a failed login must
  // stay on the page and show the error, never bounce with ?next=.
  const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1];
  fetch('/api/session-login/', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
    body: JSON.stringify({ username, password }),
  })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showToast(typeof data.error === 'string' ? data.error : 'Invalid credentials.', 'error');
        return null;
      }
      return data;
    })
    .then((data) => {
      if (!data) return;
      showToast(`Welcome back, ${username}! Signed in.`);
      const next = new URLSearchParams(window.location.search).get('next') || '/';
      window.location.href = next;
    })
    .catch(() => showToast('Sign-in service unreachable. Try again later.', 'error'));
}

async function handleAuthSignup(e) {
  if (e) e.preventDefault();
  const firstName = document.getElementById('signupFirstName')?.value.trim() || '';
  const lastName = document.getElementById('signupLastName')?.value.trim() || '';
  const email = document.getElementById('signupEmail')?.value.trim() || '';
  const password = document.getElementById('signupPasswordInput')?.value || '';
  // Raw fetch on purpose: signup is anonymous and apiFetch would bounce its
  // 403/401 straight back to /login/.
  const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1];
  try {
    const res = await fetch('/api/employees/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
      body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password }),
    });
    if (!res.ok) {
      let detail = 'Registration failed. Check your details and try again.';
      try {
        const data = await res.json();
        detail = data.error || detail;
        if (Array.isArray(detail)) detail = detail.join(' ');
        else if (typeof detail === 'object') detail = JSON.stringify(detail);
      } catch (_) { /* keep default */ }
      showToast(detail, 'error');
      return;
    }
    window.location.href = '/login/?next=/';
  } catch (err) {
    showToast('Sign-up service unreachable. Try again later.', 'error');
  }
}

function navigateToLogin(mode = 'login') {
  const currentPath = window.location.pathname.toLowerCase();
  const isFileProtocol = window.location.protocol === 'file:';

  if (isFileProtocol || currentPath.endsWith('.html')) {
    window.location.href = `login.html#${mode}`;
  } else {
    window.location.href = `/login/#${mode}`;
  }
}

function signOut() {
  showToast('Signing out of corporate session...');
  apiFetch('/api/session-logout/', { method: 'POST' })
    .catch(() => {})
    .finally(() => navigateToLogin('login'));
}

// ==========================================================================
// Audit Logs View Handlers
// ==========================================================================
let activeLogTabCategory = 'all';

function filterLogsByTab(category, btnElement) {
  activeLogTabCategory = category;
  const tabs = document.querySelectorAll('#view-logs .pill-tabs-container .tab-pill, #view-logs .claims-subtabs-bar .claims-subtab');
  tabs.forEach(tab => tab.classList.remove('active'));
  if (btnElement) {
    btnElement.classList.add('active');
  }

  const categorySelect = document.getElementById('auditCategoryFilter');
  if (categorySelect) {
    categorySelect.value = category === 'all' ? '' : category;
  }

  filterAuditLogs();
}

function filterAuditLogs() {
  const searchInput = document.getElementById('auditSearchInput');
  const categorySelect = document.getElementById('auditCategoryFilter');
  const adminSelect = document.getElementById('auditAdminFilter');

  const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
  const selectedCategory = categorySelect ? categorySelect.value : (activeLogTabCategory === 'all' ? '' : activeLogTabCategory);
  const selectedAdmin = adminSelect ? adminSelect.value : '';

  const rows = document.querySelectorAll('#auditLogsTableBody tr');
  let visibleCount = 0;

  rows.forEach(row => {
    const rowCategory = row.getAttribute('data-category') || '';
    const rowAdmin = row.getAttribute('data-admin') || '';
    const rowText = row.textContent.toLowerCase();

    const matchesCategory = !selectedCategory || selectedCategory === 'all' || rowCategory.toLowerCase() === selectedCategory.toLowerCase();
    const matchesAdmin = !selectedAdmin || rowAdmin.toLowerCase().includes(selectedAdmin.toLowerCase());
    const matchesQuery = !query || rowText.includes(query);

    if (matchesCategory && matchesAdmin && matchesQuery) {
      row.style.display = '';
      visibleCount++;
    } else {
      row.style.display = 'none';
    }
  });

  const paginationInfo = document.getElementById('auditPaginationInfo');
  if (paginationInfo) {
    const liveTotal = typeof auditLiveTotal !== 'undefined' && auditLiveTotal ? auditLiveTotal : 1482;
    paginationInfo.textContent = `Showing ${visibleCount} of ${liveTotal.toLocaleString()} logged admin events`;
  }
}

// Attendance register export: same downloadCsv helper as audit export.
// Live rows when the table holds them, demo sample otherwise. Same shape.
function exportAttendanceRegister() {
  const body = document.getElementById('attendanceTableBody');
  const live = body ? Array.from(body.querySelectorAll('tr[data-live="true"]')) : [];
  const rows = [['Date', 'Employee', 'Clock In', 'Clock Out', 'Hours']];
  if (live.length) {
    live.forEach((tr) => {
      rows.push(Array.from(tr.querySelectorAll('td')).map((td) => td.textContent.trim()));
    });
  } else {
    rows.push(['2026-09-13', 'Sample Instructor', '09:00', '17:00', '8.00']);
  }
  downloadCsv(`kumon_ems_attendance_${new Date().toISOString().slice(0, 10)}.csv`, rows);
  showToast(live.length ? 'Attendance register exported.' : 'Attendance register exported (demo sample).');
}

function downloadCsv(filename, rows) {
  const csvContent = 'data:text/csv;charset=utf-8,' + rows.map((e) => e.map((i) => `"${i}"`).join(',')).join('\n');
  const link = document.createElement('a');
  link.setAttribute('href', encodeURI(csvContent));
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function exportAuditLogs() {
  downloadCsv(
    `kumon_ems_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`,
    [
      ['Timestamp', 'Administrator', 'Action Class', 'Action', 'Target Record', 'Details', 'Status', 'Audit ID'],
      ['2026-06-09 14:32:00', 'Marcus Williams (Admin)', 'Personnel', 'Added Employee: Sofia Taylor', 'EMP-10482', 'Created employee profile, issued portal credentials', 'Completed', 'LOG-9482'],
    ['2026-06-09 11:15:00', 'Elena Rostova (Admin)', 'Leaves', 'Approved Leave Request', 'EMP-10291', 'Approved 3 days Medical Leave', 'Approved', 'LOG-9481'],
    ['2026-06-08 16:45:00', 'Marcus Williams (Admin)', 'Personnel', 'Promoted Staff: Marcus Chen', 'EMP-10334', 'Promoted to Lead Instructor', 'Completed', 'LOG-9480'],
    ['2026-06-08 10:20:00', 'David Kim (Admin)', 'Claims', 'Approved Expense Claim', 'CLM-2026-088', 'Educational materials reimbursement ($420.50)', 'Disbursed', 'LOG-9479'],
    ['2026-06-07 15:10:00', 'Elena Rostova (Admin)', 'Shifts', 'Modified Shift Roster', 'ROSTER-2026-W24', 'Reassigned 12 instructors to Morning Shift', 'Applied', 'LOG-9478'],
    ['2026-06-07 09:30:00', 'Marcus Williams (Admin)', 'Claims', 'Disbursed Advance Pay', 'ADV-2026-014', 'Approved emergency payroll advance ($800.00)', 'Disbursed', 'LOG-9477'],
    ['2026-06-06 17:00:00', 'Elena Rostova (Admin)', 'Grievance', 'Resolved Grievance Case', 'GRV-4091', 'Mediation completed and agreed', 'Resolved', 'LOG-9476'],
    ['2026-06-06 13:40:00', 'Marcus Williams (Admin)', 'Personnel', 'Transferred Employee Center', 'EMP-10255', 'Transferred to West Campus Center', 'Completed', 'LOG-9475'],
    ['2026-06-05 18:00:00', 'System Bot', 'Leaves', 'Accrued Monthly Leave Balances', 'ALL INSTRUCTORS', 'Automated 1.5 days annual leave accrual', 'Executed', 'LOG-9474'],
    ['2026-06-05 11:25:00', 'David Kim (Admin)', 'Claims', 'Rejected Non-Compliant Claim', 'CLM-2026-079', 'Rejected fuel claim missing tax invoice', 'Rejected', 'LOG-9473']
    ]
  );
}

// ==========================================================================
// Live API wiring: dashboard summary + employee directory
// ==========================================================================

// Minimal toast (showToast is called across this file but had no definition;
// keep the static demo values on screen when the API is unreachable).
if (typeof window.showToast !== 'function') {
  window.showToast = function (message, type) {
    let toast = document.getElementById('liveToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'liveToast';
      toast.style.cssText =
        'position:fixed;bottom:24px;right:24px;z-index:9999;' +
        'background:#0f172a;color:#fff;padding:12px 16px;border-radius:8px;' +
        'font-size:14px;max-width:320px;box-shadow:0 8px 24px rgba(0,0,0,.25);';
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.background = type === 'error' ? '#991b1b' : '#0f172a';
    toast.style.display = 'block';
    clearTimeout(window.__liveToastTimer);
    window.__liveToastTimer = setTimeout(() => {
      toast.style.display = 'none';
    }, 4000);
  };
}

// Public aggregate counts for the landing page; on failure the static demo
// values stay but the badge + error toast say so LOUDLY (no silent fallback).
function loadDashboardSummary() {
  apiFetch('/api/dashboard-summary/', { headers: { Accept: 'application/json' } })
    .then((res) => {
      if (!res.ok) throw new Error('summary unavailable');
      return res.json();
    })
    .then((data) => {
      setApiMode('live');
      const values = document.querySelectorAll(
        '#view-dashboard .kpi-cards-4grid .kpi-card .kpi-value'
      );
      if (values.length >= 4) {
        values[0].textContent = data.total_employees;
        // values[1] (applicants) has no API source; leave the demo value.
        values[2].textContent = String(
          (data.approved_leaves || 0) + (data.pending_leaves || 0)
        ).padStart(2, '0');
        values[3].textContent = String(data.pending_leaves || 0).padStart(2, '0');
      }
    })
    .catch((err) => {
      if (err && err.message === 'auth') return; // apiFetch already redirected
      setApiMode('demo');
      showToast('API unreachable — showing demo data', 'error');
    });
}

// Live employee directory keyed by lowercase full name (reused by the leave
// modal to resolve an applicant to an employee id). Auth-only endpoint:
// logged-out visitors are sent to the canonical login page.
const employeeNameIndex = {};

function loadEmployeeDirectory() {
  const list = document.getElementById('employeeRosterList');
  if (!list) return;
  apiFetch('/api/employees/', { headers: { Accept: 'application/json' } })
    .then((res) => {
      if (!res.ok) throw new Error('directory unavailable');
      return res.json();
    })
    .then(async (data) => {
      setApiMode('live');
      const rows = Array.isArray(data) ? data : data.results || [];
      let deptById = {};
      try {
        const dRes = await apiFetch('/api/departments/');
        const dData = await dRes.json();
        const dRows = Array.isArray(dData) ? dData : dData.results || [];
        dRows.forEach((d) => { deptById[d.id] = d.name || ''; });
      } catch (_) { /* dept filter falls back to blank */ }
      list.innerHTML = '';
      rows.forEach((emp) => {
        const fullName = `${emp.first_name || ''} ${emp.last_name || ''}`.trim();
        employeeNameIndex[fullName.toLowerCase()] = emp.id;
        const card = document.createElement('div');
        card.className = 'roster-accordion-card';
        card.setAttribute('data-live', 'true');
        card.setAttribute('data-dept', deptById[emp.department] || '');
        card.setAttribute('data-role', emp.role || '');
        card.setAttribute(
          'data-status',
          emp.is_active === false ? 'On Leave' : 'Present Today'
        );
        card.innerHTML =
          `<div class="acc-summary" onclick="toggleAccordion(this)">` +
          `<div class="acc-left">` +
          `<strong class="acc-name">${escapeHtml(fullName)}</strong>` +
          `<span class="acc-role">${escapeHtml(emp.role || '')} &bull; ${escapeHtml(emp.email || '')}</span>` +
          `</div>` +
          `<div class="acc-right">` +
          `<span class="penpot-badge ${emp.is_active === false ? 'badge-leave' : 'badge-present'}">` +
          `${emp.is_active === false ? 'On Leave' : 'Present Today'}</span>` +
          `</div></div>` +
          `<div class="acc-expanded-body" hidden>` +
          `<div class="acc-col"><span class="col-head">CONTACT</span>` +
          `<div class="perf-text">${escapeHtml(emp.email || '')}</div>` +
          `<div class="acc-btn-row">` +
          `<button class="btn btn-black-sm" onclick="switchView('employee-directory')">View Full Profile</button>` +
          `<button class="btn btn-purple-outline-sm" data-name="${escapeHtml(fullName)}" onclick="messageOnSlack(this.dataset.name)">Message on Slack</button>` +
          `</div></div></div>`;
        list.appendChild(card);
      });
      if (typeof filterDirectory === 'function') filterDirectory();
    })
    .catch((err) => {
      if (err && err.message === 'auth') return; // apiFetch already redirected
      setApiMode('demo');
      showToast('API unreachable — showing demo data', 'error');
    });
}

// ==========================================================================
// Live view wiring (H7): each loader below replaces its static demo tbody
// with live API rows, keeping the demo markup as the offline fallback.
// ==========================================================================
let liveEmployeeNameCache = null;
async function liveEmployeeNames() {
  if (liveEmployeeNameCache) return liveEmployeeNameCache;
  const res = await apiFetch('/api/employees/?page_size=50');
  if (!res.ok) throw new Error('load failed');
  const payload = await res.json();
  const rows = Array.isArray(payload) ? payload : payload.results || [];
  liveEmployeeNameCache = {};
  rows.forEach((e) => {
    liveEmployeeNameCache[e.id] = `${e.first_name || ''} ${e.last_name || ''}`.trim() || e.email || e.id;
  });
  return liveEmployeeNameCache;
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? '—' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function loadAttendanceView() {
  const body = document.getElementById('attendanceTableBody');
  if (!body) return;
  const demo = body.innerHTML;
  body.innerHTML = '<tr><td colspan="5">Loading…</td></tr>';
  try {
    const res = await apiFetch('/api/attendance/?page_size=50');
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to ids */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5">No records yet.</td></tr>';
    } else {
      rows.forEach((a) => {
        const open = !a.clock_out;
        const tr = document.createElement('tr');
        tr.setAttribute('data-live', 'true');
        tr.innerHTML =
          `<td><div class="bold-title">${escapeHtml(String(names[a.employee] || a.employee || ''))}</div>` +
          `<div class="sub-role">${escapeHtml(String(a.date || ''))}</div></td>` +
          `<td>—</td><td>${escapeHtml(fmtTime(a.clock_in))}</td><td>${escapeHtml(fmtTime(a.clock_out))}</td>` +
          `<td><span class="penpot-badge ${open ? 'badge-present' : 'badge-pending'}">` +
          `${open ? '● Clocked in' : 'Complete'}</span></td>`;
        body.appendChild(tr);
      });
    }
    setApiMode('live');
  } catch (e) { body.innerHTML = demo; setApiMode('demo'); showToast('Attendance unreachable — showing demo data', 'error'); }
}

async function loadShiftRosterView() {
  const body = document.getElementById('shiftRosterTableBody');
  if (!body) return;
  try {
    const res = await apiFetch('/api/shift-rosters/?page_size=50');
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to ids */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5">No records yet.</td></tr>';
    } else {
      rows.forEach((r) => {
        const tr = document.createElement('tr');
        tr.setAttribute('data-live', 'true');
        tr.dataset.employee = r.employee || '';
        tr.dataset.workDate = r.work_date || '';
        tr.innerHTML =
          `<td><div class="bold-title">${escapeHtml(String(names[r.employee] || r.employee || 'Unassigned'))}</div></td>` +
          `<td>${escapeHtml(String(r.work_date || '—'))}</td>` +
          `<td>${escapeHtml(String(r.shift_type || 'General'))}</td>` +
          `<td>${escapeHtml(String(r.start_time || ''))} – ${escapeHtml(String(r.end_time || ''))}</td>` +
          `<td><span data-conflict-for="${escapeHtml(String(r.id || ''))}">—</span></td>`;
        body.appendChild(tr);
      });
    }
    setApiMode('live');
    refreshShiftConflictBadges();
  } catch (e) { setApiMode('demo'); showToast('Shift roster unreachable — showing demo data', 'error'); }
}

async function refreshShiftConflictBadges() {
  const body = document.getElementById('shiftRosterTableBody');
  if (!body) return;
  for (const tr of body.querySelectorAll('tr[data-live="true"]')) {
    const emp = tr.dataset.employee;
    const day = tr.dataset.workDate;
    if (!emp || !day) continue;
    try {
      const res = await apiFetch(`/api/shift-rosters/conflicts/?employee=${encodeURIComponent(emp)}&date=${encodeURIComponent(day)}`);
      if (!res.ok) continue;
      const payload = await res.json();
      if ((payload.conflicts || []).length) {
        const cell = tr.querySelector('[data-conflict-for]');
        if (cell) cell.textContent = `⚠ ${payload.conflicts.length} leave clash`;
      }
    } catch (_) { /* badge stays clear */ }
  }
}

async function loadPayrollView() {
  const body = document.getElementById('payrollRunsTableBody');
  if (!body) return;
  try {
    const res = await apiFetch('/api/payroll-runs/?page_size=50');
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const runs = Array.isArray(payload) ? payload : payload.results || [];
    let items = [];
    try {
      const itemRes = await apiFetch('/api/payroll-items/?page_size=50');
      if (itemRes.ok) {
        const itemPayload = await itemRes.json();
        items = Array.isArray(itemPayload) ? itemPayload : itemPayload.results || [];
      }
    } catch (_) { /* lines stay zeroed */ }
    body.innerHTML = '';
    if (!runs.length) {
      body.innerHTML = '<tr><td colspan="4">No records yet.</td></tr>';
    } else {
      runs.forEach((run) => {
        const lines = items.filter((i) => i.payroll_run === run.id);
        const total = lines.reduce((sum, i) => sum + Number(i.net_pay || 0), 0);
        const tr = document.createElement('tr');
        tr.setAttribute('data-live', 'true');
        tr.innerHTML =
          `<td>${escapeHtml(String(run.pay_period_start || ''))} – ${escapeHtml(String(run.pay_period_end || ''))}</td>` +
          `<td>${run.is_processed ? 'Yes' : 'No'}</td>` +
          `<td>${lines.length}</td>` +
          `<td>${escapeHtml(total.toFixed(2))}</td>`;
        body.appendChild(tr);
      });
    }
    setApiMode('live');
  } catch (e) {
    const wrap = document.getElementById('payrollLiveWrap');
    if (wrap) wrap.style.display = 'none';
    setApiMode('demo');
    showToast('Payroll unreachable — showing demo data', 'error');
  }
}

async function loadAuditView() {
  const body = document.getElementById('auditLogsTableBody');
  if (!body) return;
  const demo = body.innerHTML;
  body.innerHTML = '<tr><td colspan="7">Loading…</td></tr>';
  try {
    const res = await apiFetch('/api/audit-logs/?page_size=50');
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    auditLiveTotal = typeof payload.count === 'number' ? payload.count : rows.length;
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to System */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7">No records yet.</td></tr>';
    } else {
      rows.forEach((log) => {
        const who = names[log.employee] || 'System';
        const when = log.timestamp ? new Date(log.timestamp).toLocaleString() : '—';
        const tr = document.createElement('tr');
        tr.setAttribute('data-live', 'true');
        tr.setAttribute('data-category', 'General');
        tr.setAttribute('data-admin', who);
        tr.innerHTML =
          `<td><div class="claims-applicant-cell"><div class="claims-applicant-info">` +
          `<strong>${escapeHtml(String(who))}</strong></div></div></td>` +
          `<td>General</td><td>${escapeHtml(String(when))}</td>` +
          `<td>${escapeHtml(String(log.action || ''))}</td><td>—</td>` +
          `<td><span class="penpot-badge badge-present">Logged</span></td>` +
          `<td style="text-align: right;">${escapeHtml(String(log.id || '').slice(0, 8))}</td>`;
        body.appendChild(tr);
      });
    }
    setApiMode('live');
  } catch (e) { body.innerHTML = demo; setApiMode('demo'); showToast('Audit log unreachable — showing demo data', 'error'); }
}

// Audit pager (D34): ?page=N against /api/audit-logs/, same live row shape
// as loadAuditView, demo markup restored when the API is unreachable.
let auditPagerPage = 1;
const AUDIT_PAGE_SIZE = 10;
// Live total from the last audit fetch; filterAuditLogs falls back to the
// static demo total until the first live page lands.
let auditLiveTotal = 0;

function auditPagerStep(delta) {
  auditPagerGoto(auditPagerPage + delta);
}

function auditCategory(action) {
  const text = String(action || '').toLowerCase();
  if (text.includes('leave')) return 'Leave';
  if (text.includes('payroll') || text.includes('overtime') || text.includes('claim') || text.includes('advance')) return 'Payroll';
  if (text.includes('roster') || text.includes('shift') || text.includes('swap') || text.includes('attendance') || text.includes('clock')) return 'Roster';
  if (text.includes('swap') || text.includes('grievance')) return 'Grievance';
  if (text.includes('employee') || text.includes('department') || text.includes('resign') || text.includes('purged')) return 'People';
  return 'General';
}

function buildAuditRow(log, names) {
  const who = names[log.employee] || 'System';
  const category = auditCategory(log.action);
  const when = log.timestamp ? new Date(log.timestamp).toLocaleString() : '—';
  const tr = document.createElement('tr');
  tr.setAttribute('data-live', 'true');
  tr.setAttribute('data-category', category);
  tr.setAttribute('data-admin', who);
  tr.innerHTML =
    `<td><div class="claims-applicant-cell"><div class="claims-applicant-info">` +
    `<strong>${escapeHtml(String(who))}</strong></div></div></td>` +
    `<td>${escapeHtml(category)}</td><td>${escapeHtml(String(when))}</td>` +
    `<td>${escapeHtml(String(log.action || ''))}</td><td>—</td>` +
    `<td><span class="penpot-badge badge-present">Logged</span></td>` +
    `<td style="text-align: right;">${escapeHtml(String(log.id || '').slice(0, 8))}</td>`;
  return tr;
}

async function auditPagerGoto(page) {
  if (page < 1) return;
  const body = document.getElementById('auditLogsTableBody');
  if (!body) return;
  const demo = body.dataset.demoHtml || body.innerHTML;
  body.dataset.demoHtml = demo;
  try {
    const res = await apiFetch(`/api/audit-logs/?page=${page}&page_size=${AUDIT_PAGE_SIZE}`);
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    const total = typeof payload.count === 'number' ? payload.count : rows.length;
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to System */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7">No audit events on this page yet.</td></tr>';
    } else {
      rows.forEach((log) => body.appendChild(buildAuditRow(log, names)));
    }
    const info = document.getElementById('auditPaginationInfo');
    if (info) info.textContent = `Showing page ${page} of ${total} live logged admin events`;
    auditPagerPage = page;
    auditLiveTotal = total;
    markPagerActive('audit', page);
    const prev = document.getElementById('auditPrevBtn');
    if (prev) {
      prev.disabled = page <= 1;
      prev.style.opacity = page <= 1 ? '0.5' : '';
      prev.style.cursor = page <= 1 ? 'not-allowed' : '';
    }
    setApiMode('live');
  } catch (e) {
    body.innerHTML = demo;
    setApiMode('demo');
    showToast('Audit page unreachable — showing demo data', 'error');
  }
}


