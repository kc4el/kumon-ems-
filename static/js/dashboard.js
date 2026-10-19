/* ==========================================================================
   Kumon EMS - Interactive Logic & State Management
   ========================================================================== */


document.addEventListener('DOMContentLoaded', () => {
  initBrandLogo();
  initRememberedLogin();
  initNavigation();
  initializeCurrentDateLabels();
  loadDashboardSummary();
  loadDashboardAttendance();
  loadEmployeeDirectory();
  loadGrievanceView();
  populateRosterEmployeeOptions();
  loadLeaveRegister();
  claimsPagerGoto('pending', 1);
  claimsPagerGoto('history', 1);
  loadClaimStatuses();
  loadClaimsSummary();
  updateBatchApproveCount();
  loadAdvancesView();
  loadEmployeeInbox();
  loadAttendanceView();
  loadShiftRosterView();
  initializeShiftEditorDate();
  loadMasterShiftCalendar();
  loadPayrollView();
  loadAuditView();
  applySettingsA11yOnLoad();
  initDashboardWidgets();
  loadActivityFeed();
  refreshNotifBell();
  initTour();
  populatePromotionTransferDropdowns();
  populateOnboardingOptions();
  startDashboardLiveRefresh();
});

let dashboardRefreshTimer = null;
let dashboardRefreshInFlight = false;

async function refreshDashboardLiveData() {
  if (dashboardRefreshInFlight || document.hidden) return;
  const dashboardView = document.getElementById('view-dashboard');
  if (!dashboardView) return;
  dashboardRefreshInFlight = true;
  try {
    // Request registers also change while HR is viewing another section.
    // Keep these lists current without refreshing unrelated dashboard data.
    if (!dashboardView.classList.contains('active')) {
      await Promise.all([loadLeaveRegister(), loadGrievanceView(), loadAdvancesView()]);
      return;
    }
    await Promise.all([
      loadDashboardSummary(),
      loadDashboardAttendance(),
      loadLeaveRegister(),
      loadGrievanceView(),
      loadAdvancesView(),
      loadClaimsSummary(),
    ]);
  } finally {
    dashboardRefreshInFlight = false;
  }
}

function startDashboardLiveRefresh() {
  if (dashboardRefreshTimer) clearInterval(dashboardRefreshTimer);
  const refreshEveryMs = 30000;
  dashboardRefreshTimer = setInterval(() => {
    if (!document.hidden) refreshDashboardLiveData();
  }, refreshEveryMs);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !dashboardRefreshInFlight) refreshDashboardLiveData();
  });
}

function initializeCurrentDateLabels() {
  const today = new Date();
  const dateText = today.toLocaleDateString(undefined, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
  const monthText = today.toLocaleDateString(undefined, {
    month: 'long', year: 'numeric',
  });
  const isoDate = localDateIso(today);
  const dateLabel = document.getElementById('dashboardTodayLabel');
  const monthLabel = document.getElementById('dashboardMonthLabel');
  const attendanceDate = document.getElementById('attendanceDateLabel');
  const attendanceMonth = document.getElementById('attendanceMonthLabel');
  const picker = document.getElementById('shiftDatePicker');
  if (dateLabel) dateLabel.textContent = dateText;
  if (monthLabel) monthLabel.textContent = monthText;
  if (attendanceDate) attendanceDate.textContent = `Attendance for ${dateText}`;
  if (attendanceMonth) attendanceMonth.textContent = monthText;
  if (picker && !picker.value) picker.value = isoDate;
  initAttendanceCalendar();
}

function localDateIso(date = new Date()) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
}

let attendanceCalendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let attendanceSelectedDate = localDateIso();
let attendanceLoggedDates = new Set();

function initAttendanceCalendar() {
  const grid = document.getElementById('attendanceCalendarGrid');
  if (!grid || grid.dataset.ready) return;
  grid.dataset.ready = 'true';
  document.getElementById('attendancePrevMonth')?.addEventListener('click', () => {
    attendanceCalendarMonth.setMonth(attendanceCalendarMonth.getMonth() - 1);
    attendanceSelectedDate = `${attendanceCalendarMonth.getFullYear()}-${String(attendanceCalendarMonth.getMonth() + 1).padStart(2, '0')}-01`;
    renderAttendanceCalendar();
  });
  document.getElementById('attendanceNextMonth')?.addEventListener('click', () => {
    attendanceCalendarMonth.setMonth(attendanceCalendarMonth.getMonth() + 1);
    attendanceSelectedDate = `${attendanceCalendarMonth.getFullYear()}-${String(attendanceCalendarMonth.getMonth() + 1).padStart(2, '0')}-01`;
    renderAttendanceCalendar();
  });
  renderAttendanceCalendar();
}

function renderAttendanceCalendar() {
  const grid = document.getElementById('attendanceCalendarGrid');
  const label = document.getElementById('attendanceMonthLabel');
  if (!grid) return;
  const year = attendanceCalendarMonth.getFullYear();
  const month = attendanceCalendarMonth.getMonth();
  if (label) label.textContent = attendanceCalendarMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }).toUpperCase();
  grid.querySelectorAll('.attendance-calendar-cell').forEach((cell) => cell.remove());
  for (let i = 0; i < new Date(year, month, 1).getDay(); i += 1) {
    const placeholder = document.createElement('span');
    placeholder.className = 'attendance-calendar-cell attendance-calendar-placeholder';
    placeholder.setAttribute('aria-hidden', 'true');
    grid.appendChild(placeholder);
  }
  const today = localDateIso();
  const lastDay = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= lastDay; day += 1) {
    const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const isLogged = attendanceLoggedDates.has(iso);
    const cell = document.createElement('span');
    cell.className = `attendance-calendar-cell attendance-calendar-day${iso === attendanceSelectedDate ? ' day-active' : ''}${iso === today ? ' day-today' : ''}${isLogged ? ' day-logged' : ''}`;
    cell.textContent = String(day);
    cell.title = isLogged ? `Attendance logged for ${iso}` : `Show attendance for ${iso}`;
    cell.addEventListener('click', () => {
      attendanceSelectedDate = iso;
      renderAttendanceCalendar();
      filterAttendanceRegisterByDate();
    });
    grid.appendChild(cell);
  }
  filterAttendanceRegisterByDate();
}

function filterAttendanceRegisterByDate() {
  const body = document.getElementById('attendanceTableBody');
  const label = document.getElementById('attendanceDateLabel');
  if (!body) return;
  const rows = body.querySelectorAll('tr[data-attendance-date]');
  let visibleCount = 0;
  rows.forEach((row) => {
    const matches = row.dataset.attendanceDate === attendanceSelectedDate;
    row.style.display = matches ? '' : 'none';
    if (matches) visibleCount++;
  });
  const existingEmpty = body.querySelector('.attendance-empty-row');
  if (existingEmpty) existingEmpty.remove();

  if (rows.length > 0 && visibleCount === 0) {
    const tr = document.createElement('tr');
    tr.className = 'attendance-empty-row';
    tr.innerHTML = `<td colspan="5" style="text-align:center; padding: 24px; color: #64748b;">No attendance records for ${escapeHtml(formatLeaveDate(attendanceSelectedDate))}.</td>`;
    body.appendChild(tr);
  }
  if (label) {
    const formatted = typeof formatLeaveDate === 'function' ? formatLeaveDate(attendanceSelectedDate) : attendanceSelectedDate;
    label.textContent = `${formatted} • Attendance register`;
  }
}

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
// setApiMode tracks the dashboard summary request, not unrelated panel errors.
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
  }).then(async (res) => {
    // Logged-out viewers bouncing around /login/?next=/login/ loop forever:
    // serve the login page instead of redirecting to itself.
    const loginPage = window.location.pathname.startsWith('/login') || window.location.pathname.startsWith('/hr/login');
    if ((res.status === 401 || res.status === 403) && loginPage) return res;
    const loginPath = window.location.pathname.startsWith('/hr') ? '/hr/login/' : '/login/';
    let authenticationRequired = res.status === 401;
    if (res.status === 403) {
      const body = await res.clone().json().catch(() => null);
      authenticationRequired = body?.error === 'Authentication required.';
    }
    if (authenticationRequired) { window.location.href = loginPath + '?next=' + encodeURIComponent(window.location.pathname); throw new Error("auth"); }
    return res;
  });
}

function setApiMode(mode) {
  if (mode === 'live') {
    dashboardSummaryFailures = 0;
  } else if (mode === 'offline') {
    dashboardSummaryFailures += 1;
    mode = dashboardSummaryFailures < 2 ? 'retrying' : 'offline';
  }
  document.body.dataset.api = mode;
  const badge = document.getElementById('apiModeBadge');
  if (badge) {
    const states = {
      live: ['Data live', 'badge-present'],
      retrying: ['Retrying', 'badge-pending'],
      offline: ['Data issue', 'badge-resigned'],
    };
    const [label, badgeClass] = states[mode] || states.retrying;
    badge.textContent = label;
    badge.className = `penpot-badge ${badgeClass}`;
  }
}

let dashboardSummaryFailures = 0;
let dashboardSummaryInFlight = false;
let dashboardSummaryRetryTimer = null;

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
  'employee-directory': { root: 'Employees', active: 'Employee List' },
  'employee-manage': { root: 'Employees', active: 'Manage Staff' },
  'employee-grievance': { root: 'Employees', active: 'Grievance Tracker' },
  'attendance-daily': { root: 'Attendance', active: 'Daily Log' },
  'attendance-shift': { root: 'Attendance', active: 'Shift Management' },
  'attendance-leave': { root: 'Attendance', active: 'Leave Management' },
  'claims': { root: 'Claims', active: 'Pending Claims' },
  'messages': { active: 'Messages & Channels' },
  'logs': { active: 'Audit & Activity Logs' },
  'settings': { active: 'Settings' },
  'profile': { active: 'My Profile' },
  'my-details': { active: 'My Details' },
  'reports': { active: 'Reports & Analytics' }
};


function initNavigation() {
  const initialStream = document.getElementById('chatStreamMessages');
  if (initialStream) initialStream.innerHTML = '<div class="chat-loading-state">Choose a conversation to load its messages.</div>';
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
      (viewName === 'logs' && dataView === 'logs') ||
      ((viewName === 'profile' || viewName === 'my-details') && dataView === 'profile') ||
      (viewName === 'settings' && dataView === 'settings')) {
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
    if (viewName === 'settings') {
      loadSettingsView();
    }
    if (viewName === 'profile' || viewName === 'my-details') {
      loadAccountProfile();
    }
    if (viewName === 'dashboard') {
      refreshDashboardLiveData();
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
  const view = document.getElementById("view-settings");
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

function formatAuditActionText(action) {
  if (!action) return "update";
  const str = String(action);
  if (str.startsWith("resigned ")) {
    const parts = str.split(",");
    const datePart = (parts[0] || "").trim();
    const purgePart = (parts[1] || "").trim();
    return `Employee ${datePart} (${purgePart} • Access revoked)`;
  }
  return str;
}

// D6: "Today" activity feed from the live audit log. Uses raw fetch (not
// apiFetch) so a logged-out 401/403 renders "Activity unavailable." instead
// of triggering apiFetch's login redirect; the feed never bounces to login.
async function loadActivityFeed() {
  const list = document.getElementById("activityFeedList");
  if (!list) return;
  try {
    const res = await fetch("/api/audit-logs/?page_size=5", { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("feed failed");
    const payload = await res.json();
    const rows = (payload.results || payload || []);
    let totalLen = 0;
    const maxItems = 3;
    const filteredRows = [];
    for (const r of rows) {
      if (filteredRows.length >= maxItems) break;
      const textLen = (formatAuditActionText(r.action) || "").length;
      if (filteredRows.length === 2 && (totalLen > 70 || textLen > 40)) break;
      filteredRows.push(r);
      totalLen += textLen;
    }
    list.innerHTML = filteredRows.length
      ? filteredRows.map((r) => `<li>${escapeHtml(formatAuditActionText(r.action))} <span>${escapeHtml(String(r.timestamp || "").slice(0, 16).replace("T", " "))}</span></li>`).join("")
      : "<li>No activity yet today.</li>";
  } catch (e) { list.innerHTML = "<li>Activity unavailable.</li>"; }
}

// Short first-run guide; only points to panels backed by current app flows.
const KUMON_TOUR_KEY = "kumon.tourSeen.v2";
const KUMON_TOUR_STEPS = [
  { view: "dashboard", text: "Your home page brings today’s activity and team summaries together. Use the left menu to move between people, attendance, requests, and account tools." },
  { view: "employee-directory", text: "Search the directory to find an employee. Open a record to review the details and available HR actions." },
  { view: "attendance-daily", text: "Review the daily attendance register and move between dates to check clock-in and clock-out records." },
  { view: "attendance-leave", text: "Review leave requests and submit your own request from the employee portal." },
  { view: "settings", text: "Set notification and display preferences. Staff administrators can also manage company rules and roster imports here." },
  { view: "profile", text: "Update your own account details, set a new password, and enable authenticator-based two-factor sign-in." },
];
let kumonTourIndex = -1;
function startTour() {
  try { localStorage.removeItem(KUMON_TOUR_KEY); } catch (e) { }
  kumonTourIndex = -1; nextTourStep();
}
function nextTourStep() {
  kumonTourIndex += 1;
  if (kumonTourIndex >= KUMON_TOUR_STEPS.length) { endTour(); return; }
  const step = KUMON_TOUR_STEPS[kumonTourIndex];
  switchView(step.view);
  showTourBubble(step, kumonTourIndex + 1, KUMON_TOUR_STEPS.length);
}
function previousTourStep() {
  if (kumonTourIndex <= 0) return;
  kumonTourIndex -= 2;
  nextTourStep();
}
function endTour() {
  kumonTourIndex = -1;
  const b = document.getElementById("tourBubble");
  if (b) b.remove();
  try { localStorage.setItem(KUMON_TOUR_KEY, "1"); } catch (e) { }
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
  title.textContent = "Quick tour";
  head.appendChild(title);
  head.appendChild(badge);
  const p = document.createElement("p");
  p.className = "tour-text";
  p.textContent = step.text;
  p.setAttribute("aria-live", "polite");
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
  const back = document.createElement("button");
  back.type = "button";
  back.className = "btn btn-outline-gray";
  back.textContent = "Back";
  back.disabled = n === 1;
  back.addEventListener("click", previousTourStep);
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "btn-black-sm";
  skip.textContent = "Skip";
  skip.addEventListener("click", endTour);
  const next = document.createElement("button");
  next.type = "button";
  next.className = "btn-blue-sm";
  next.textContent = n >= total ? "Finish" : "Continue";
  next.addEventListener("click", nextTourStep);
  foot.appendChild(back);
  foot.appendChild(skip);
  foot.appendChild(next);
  b.appendChild(head);
  b.appendChild(p);
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
    btn.textContent = "Take a quick tour";
    btn.addEventListener("click", startTour);
    if (settings && settings.nextSibling) settings.parentElement.insertBefore(btn, settings.nextSibling);
    else if (settings) settings.parentElement.appendChild(btn);
    else view.prepend(btn);
  }
  let seen = null;
  try { seen = localStorage.getItem(KUMON_TOUR_KEY); } catch (e) { seen = null; }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && kumonTourIndex >= 0) endTour();
  });
  if (!seen && view) setTimeout(startTour, 1100);
}

// Accordion toggle for Employee Directory
function focusRosterProfile(button) {
  const card = button?.closest('.roster-accordion-card');
  if (!card) return;
  if (!card.classList.contains('open')) {
    const summary = card.querySelector('.acc-summary');
    if (summary) toggleAccordion(summary);
  }
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  card.classList.add('profile-focus');
  window.setTimeout(() => card.classList.remove('profile-focus'), 900);
}

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
    populatePromotionTransferDropdowns();
  } else if (mode === 'transfer') {
    if (title) title.textContent = 'Transfer employee';
    if (subtitle) subtitle.textContent = 'Move a person to a new team or work location and keep the effective date and rationale on the record.';
    if (promoteContainer) promoteContainer.style.display = 'none';
    if (transferContainer) transferContainer.style.display = 'block';
    if (removeContainer) removeContainer.style.display = 'none';
    populatePromotionTransferDropdowns();
  } else if (mode === 'remove') {
    if (title) title.textContent = 'Employee Offboarding Processing Wizard';
    if (subtitle) subtitle.textContent = 'Complete the following exit procedures for the departing employee.';
    if (promoteContainer) promoteContainer.style.display = 'none';
    if (transferContainer) transferContainer.style.display = 'none';
    if (removeContainer) removeContainer.style.display = 'block';
    populateOffboardDropdown();
  }
}

// Caches for promotion & transfer dropdowns
let _activeEmployeesCache = null;
let _departmentsCache = null;

async function populatePromotionTransferDropdowns() {
  const promoteEmp = document.getElementById('promoteEmployeeSelect');
  const promoteRoleOptions = document.getElementById('promoteRoleOptions');
  const transferEmp = document.getElementById('transferEmployeeSelect');
  const transferDept = document.getElementById('transferDeptSelect');

  try {
    const [empData, deptData] = await Promise.all([
      _activeEmployeesCache ? Promise.resolve(_activeEmployeesCache) : fetchAllApiRows('/api/employees/?page_size=100&is_active=true'),
      _departmentsCache ? Promise.resolve(_departmentsCache) : fetchAllApiRows('/api/departments/?page_size=100'),
    ]);

    const emps = empData;
    const depts = deptData;
    _activeEmployeesCache = emps;
    _departmentsCache = depts;

    if (promoteRoleOptions) {
      promoteRoleOptions.replaceChildren(...[...new Set(emps.map((employee) => employee.role).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b))
        .map((role) => new Option(role, role)));
    }

    if (promoteEmp) {
      const cur = promoteEmp.value;
      promoteEmp.innerHTML = '<option value="" disabled selected>-- Select Employee --</option>';
      emps.forEach((emp) => {
        const opt = document.createElement('option');
        opt.value = emp.id;
        opt.textContent = `${emp.first_name} ${emp.last_name} (${emp.role || 'No Role'})`;
        promoteEmp.appendChild(opt);
      });
      if (cur) promoteEmp.value = cur;
    }

    if (transferEmp) {
      const cur = transferEmp.value;
      transferEmp.innerHTML = '<option value="" disabled selected>-- Select Employee --</option>';
      emps.forEach((emp) => {
        const opt = document.createElement('option');
        opt.value = emp.id;
        opt.textContent = `${emp.first_name} ${emp.last_name} (${emp.department_name || 'No Dept'})`;
        transferEmp.appendChild(opt);
      });
      if (cur) transferEmp.value = cur;
    }

    if (transferDept) {
      const cur = transferDept.value;
      transferDept.innerHTML = '<option value="" disabled selected>-- Select Department --</option>';
      depts.forEach((dept) => {
        const opt = document.createElement('option');
        opt.value = dept.id;
        opt.textContent = dept.name;
        transferDept.appendChild(opt);
      });
      if (cur) transferDept.value = cur;
    }
  } catch (err) {
    console.error('Could not load promote/transfer dropdown data', err);
  }
}

async function populateOnboardingOptions() {
  const departmentSelect = document.getElementById('onboardDepartment');
  const roleOptions = document.getElementById('onboardRoleOptions');
  const startDate = document.getElementById('onboardStartDate');
  const today = new Date();
  if (startDate && !startDate.value) {
    startDate.value = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-');
  }
  try {
    const [departments, employees] = await Promise.all([
      fetchAllApiRows('/api/departments/?page_size=100'),
      fetchAllApiRows('/api/employees/?page_size=100'),
    ]);
    if (departmentSelect) {
      departmentSelect.replaceChildren(new Option('Select Department...', ''));
      departments.forEach((department) => {
        departmentSelect.appendChild(new Option(department.name, department.id));
      });
      departmentSelect.disabled = !departments.length;
    }
    if (roleOptions) {
      roleOptions.replaceChildren(...[...new Set(employees.map((employee) => employee.role).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b))
        .map((role) => new Option(role, role)));
    }
  } catch (_) {
    if (departmentSelect) {
      departmentSelect.replaceChildren(new Option('Departments unavailable', ''));
      departmentSelect.disabled = true;
    }
    showToast('Onboarding options could not be loaded.', 'error');
  }
}

function resetPromoteForm() {
  const selEmp = document.getElementById('promoteEmployeeSelect');
  const selRole = document.getElementById('promoteRoleSelect');
  if (selEmp) selEmp.selectedIndex = 0;
  if (selRole) selRole.value = '';
}

async function handlePromotionSubmit() {
  const employeeId = document.getElementById('promoteEmployeeSelect')?.value;
  const role = document.getElementById('promoteRoleSelect')?.value;
  const payGrade = document.getElementById('promotePayGradeSelect')?.value;
  const effectiveDate = document.getElementById('promoteEffectiveDateSelect')?.value;
  const rationale = document.getElementById('promoteRationaleSelect')?.value;

  if (!employeeId) {
    showToast('Please select an employee to promote.', 'error');
    return;
  }
  if (!role) {
    showToast('Please select the new role.', 'error');
    return;
  }

  const btn = document.getElementById('btnRecordPromotion');
  if (btn) btn.disabled = true;

  try {
    const res = await apiFetch(`/api/employees/${employeeId}/promote/`, {
      method: 'POST',
      body: JSON.stringify({
        role,
        pay_grade: payGrade,
        effective_date: effectiveDate,
        rationale,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Promotion could not be recorded.');

    showToast(`Promotion recorded: promoted to ${role}!`);
    resetPromoteForm();
    _activeEmployeesCache = null;
    populatePromotionTransferDropdowns();

    const card = document.querySelector(`.roster-accordion-card[data-emp-id="${employeeId}"]`);
    if (card) {
      card.setAttribute('data-role', role);
      const roleElem = card.querySelector('.acc-role');
      if (roleElem) {
        roleElem.innerHTML = `${escapeHtml(role)} &bull; ${escapeHtml(data.email || '')}`;
      }
    }

    if (typeof loadEmployeeDirectory === 'function') loadEmployeeDirectory();
    if (typeof loadActivityFeed === 'function') loadActivityFeed();
    if (typeof loadAuditView === 'function') loadAuditView();
    if (typeof refreshNotifBell === 'function') refreshNotifBell();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function resetTransferForm() {
  const selEmp = document.getElementById('transferEmployeeSelect');
  const selDept = document.getElementById('transferDeptSelect');
  if (selEmp) selEmp.selectedIndex = 0;
  if (selDept) selDept.selectedIndex = 0;
}

async function handleTransferSubmit() {
  const employeeId = document.getElementById('transferEmployeeSelect')?.value;
  const departmentId = document.getElementById('transferDeptSelect')?.value;
  const location = document.getElementById('transferLocationSelect')?.value;
  const workMode = document.getElementById('transferWorkModeSelect')?.value;
  const effectiveDate = document.getElementById('transferEffectiveDateSelect')?.value;
  const reason = document.getElementById('transferReasonSelect')?.value;

  if (!employeeId) {
    showToast('Please select an employee to transfer.', 'error');
    return;
  }
  if (!departmentId) {
    showToast('Please select the target department.', 'error');
    return;
  }

  const btn = document.getElementById('btnRecordTransfer');
  if (btn) btn.disabled = true;

  try {
    const res = await apiFetch(`/api/employees/${employeeId}/transfer/`, {
      method: 'POST',
      body: JSON.stringify({
        department: departmentId,
        location,
        work_mode: workMode,
        effective_date: effectiveDate,
        reason,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Transfer could not be recorded.');

    showToast(`Transfer recorded: transferred to ${data.department_name || 'new department'}!`);
    resetTransferForm();
    _activeEmployeesCache = null;
    populatePromotionTransferDropdowns();

    const card = document.querySelector(`.roster-accordion-card[data-emp-id="${employeeId}"]`);
    if (card) {
      card.setAttribute('data-dept', data.department_name || '');
    }

    if (typeof loadEmployeeDirectory === 'function') loadEmployeeDirectory();
    if (typeof loadActivityFeed === 'function') loadActivityFeed();
    if (typeof loadAuditView === 'function') loadAuditView();
    if (typeof refreshNotifBell === 'function') refreshNotifBell();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

// Cache fetched employee list for the offboarding dropdown so repeat
// mode-switches do not fire redundant network requests.
let _offboardEmployees = null;

async function populateOffboardDropdown() {
  const select = document.getElementById('offboardEmployeeSelect');
  if (!select) return;
  try {
    const rows = await fetchAllApiRows('/api/employees/?page_size=100&is_active=true');
    _offboardEmployees = rows;
    // Keep the placeholder, replace the rest.
    select.innerHTML = '<option value="" selected disabled>-- Select Employee --</option>';
    rows.forEach((emp) => {
      const opt = document.createElement('option');
      opt.value = emp.id;
      opt.textContent = `${emp.first_name} ${emp.last_name}`;
      select.appendChild(opt);
    });
  } catch {
    showToast('Could not load employee list.', 'error');
  }
}

function onOffboardEmployeeSelect(select) {
  if (!_offboardEmployees) return;
  const emp = _offboardEmployees.find((e) => String(e.id) === select.value);
  const emailInput = document.getElementById('offboardEmail');
  const deptInput = document.getElementById('offboardDeptRole');
  if (emailInput) emailInput.value = emp ? emp.email : '';
  if (deptInput) deptInput.value = emp ? `${emp.role || 'N/A'} • ${emp.department_name || emp.department || 'N/A'}` : '';
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

// Offboarding handler — uses the dropdown-selected employee ID to
// DELETE via the existing soft-delete (resign) flow.
async function handleOffboardingSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const select = document.getElementById('offboardEmployeeSelect');
  const employeeId = select?.value;
  if (!employeeId) {
    showToast('Select an employee to offboard.', 'error');
    return;
  }
  // Exit docs ride validateOnboardingFile guards. Same rule, no new rule.
  for (const input of form.querySelectorAll('[data-offboard-file]')) {
    const err = input.files?.[0] ? validateOnboardingFile(input.files[0]) : null;
    if (err) {
      showToast(err, 'error');
      return;
    }
  }
  try {
    const delRes = await apiFetch(`/api/employees/${employeeId}/`, { method: 'DELETE' });
    if (!delRes.ok) throw new Error('offboard failed');
    const delData = await delRes.json().catch(() => ({}));
    if (delData.deauthed === false) {
      showToast('Offboarded, but chat/login revocation needs retry — purge will complete it.', 'error');
    } else {
      showToast('Offboarding finalized and exit clearance issued successfully!');
    }
    form.reset();
    document.getElementById('offboardEmail').value = '';
    document.getElementById('offboardDeptRole').value = '';
    _offboardEmployees = null;
    populateOffboardDropdown();

    // 1. Instantly update the employee card in-place in the directory DOM
    const card = document.querySelector(`.roster-accordion-card[data-emp-id="${employeeId}"]`);
    if (card) {
      card.setAttribute('data-status', 'Resigned');
      const badge = card.querySelector('.penpot-badge');
      if (badge) {
        badge.className = 'penpot-badge badge-resigned';
        badge.textContent = 'Resigned';
      }
    }

    // 2. Reload employee directory and name caches in background
    liveEmployeeNameCache = null;
    if (typeof loadEmployeeDirectory === 'function') loadEmployeeDirectory();

    // 3. Reload activity feed and audit logs
    if (typeof loadActivityFeed === 'function') loadActivityFeed();
    if (typeof loadAuditView === 'function') loadAuditView();

    // 4. Update notification bell and attendance
    if (typeof refreshNotifBell === 'function') refreshNotifBell();
    if (typeof loadAttendanceView === 'function') loadAttendanceView();
    if (typeof loadDashboardAttendance === 'function') loadDashboardAttendance();
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
  const password = document.getElementById('onboardPassword')?.value || '';
  const parts = fullName.split(/\s+/).filter(Boolean);
  if (parts.length < 2) {
    showToast('Enter the employee\'s first and last name.', 'error');
    return;
  }
  const lastName = parts.pop();
  const payload = {
    first_name: parts.join(' '),
    last_name: lastName,
    email,
    password,
  };
  const departmentId = form.querySelector('#onboardDepartment')?.value || '';
  const roleVal = (form.querySelector('#onboardRole')?.value || '').trim();
  if (!departmentId) {
    showToast('Select a department from the database.', 'error');
    return;
  }
  payload.department = departmentId;
  payload.date_hired = document.getElementById('onboardStartDate')?.value;
  if (roleVal) payload.role = roleVal;
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
            : data.error && typeof data.error === 'object'
              ? Object.entries(data.error).flatMap(([field, messages]) =>
                (Array.isArray(messages) ? messages : [messages]).map((message) => `${field}: ${message}`)
              ).join(' ')
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
        showToast(`Employee ${fullName || email} created. Login: ${email} | Initial password: ${password}${suffix}`);
        closeOnboardingModal();
        form.reset();
        form.querySelectorAll('[data-doc-label]').forEach((el) => { el.textContent = 'Upload File'; });
        loadEmployeeDirectory();
        loadEmployeeInbox();
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

async function loadGrievanceView() {
  const list = document.getElementById('grievanceCaseList');
  const complainant = document.getElementById('grievComplainant');
  if (!list) return;
  try {
    const [grievances, employees] = await Promise.all([
      fetchAllApiRows('/api/complaints/?page_size=100'),
      fetchAllApiRows('/api/employees/?page_size=100'),
    ]);
    if (complainant) {
      complainant.innerHTML = '<option value="">Select employee...</option>';
      employees.filter((employee) => employee.is_active !== false).forEach((employee) => {
        const option = document.createElement('option');
        option.value = employee.id;
        option.textContent = `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || employee.email;
        complainant.appendChild(option);
      });
    }
    list.innerHTML = '';
    if (!grievances.length) {
      list.innerHTML = '<p class="card-sub">No grievance cases have been filed yet.</p>';
    } else {
      grievances.forEach((grievance) => {
        const status = String(grievance.status || 'Pending');
        const statusClass = status.toLowerCase().replace(/\s+/g, '-');
        const item = document.createElement('div');
        item.className = 'grievance-case-item';
        item.innerHTML =
          `<div class="case-header-row"><strong class="case-title">Case #${escapeHtml(String(grievance.id).slice(0, 8))}: ${escapeHtml(grievance.subject)}</strong>` +
          `<span class="penpot-badge badge-${escapeHtml(statusClass)}">${escapeHtml(status)}</span></div>` +
          `<p class="case-submeta">Filed by: ${escapeHtml(grievance.employee_name || 'Anonymous Filing')} • Date: ${escapeHtml(formatLeaveDate(String(grievance.created_at || '').slice(0, 10)))}</p>` +
          `<p class="case-quote">${escapeHtml(grievance.description)}</p>`;
        list.appendChild(item);
      });
    }
    const open = grievances.filter((grievance) => !['Resolved', 'Rejected'].includes(grievance.status)).length;
    const mediation = grievances.filter((grievance) => grievance.status === 'In Mediation').length;
    const resolved = grievances.filter((grievance) => grievance.status === 'Resolved').length;
    document.getElementById('grievanceOpenCount')?.replaceChildren(String(open).padStart(2, '0'));
    document.getElementById('grievanceMediationCount')?.replaceChildren(String(mediation).padStart(2, '0'));
    document.getElementById('grievanceResolvedCount')?.replaceChildren(String(resolved).padStart(2, '0'));
  } catch (_) {
    list.innerHTML = '<p class="card-sub">Grievance data is unavailable.</p>';
    showToast('Grievance data could not be loaded.', 'error');
  }
}

// Save a grievance as a first-class database record so the tracker can reload it.
async function handleGrievanceSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const complainant = document.getElementById('grievComplainant')?.value || '';
  const category = document.getElementById('grievCategory')?.value || 'general';
  const title = document.getElementById('grievTitle')?.value.trim() || '';
  const details = document.getElementById('grievDetails')?.value.trim() || '';
  try {
    const res = await apiFetch('/api/complaints/', {
      method: 'POST',
      body: JSON.stringify({ employee: complainant || undefined, category, subject: title, description: details }),
    });
    if (!res.ok) throw new Error('file failed');
    showToast('Confidential grievance filed and assigned to HR Mediator.');
    form.reset();
    loadGrievanceView();
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
      displayEl.textContent = `Live allocation for ${label}`;
    }
    loadMasterShiftCalendar(dateVal);
    loadShiftEditorForDate(dateVal);
    showToast(`Roster updated for ${label}`);
  }
}

function stepShiftDate(offsetDays) {
  const picker = document.getElementById('shiftDatePicker');
  if (!picker) return;
  let currentDate = picker.value ? new Date(picker.value) : new Date();
  if (isNaN(currentDate.getTime())) {
    currentDate = new Date();
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
  const today = new Date();
  const todayStr = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-');
  picker.value = todayStr;
  handleShiftDateChange(todayStr);
  showToast('Reset roster view to today.');
}

function initializeShiftEditorDate() {
  const picker = document.getElementById('shiftDatePicker');
  if (!picker) return;
  const today = new Date();
  const todayStr = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-');
  picker.value = todayStr;
  const display = document.getElementById('shiftDateDisplay');
  if (display) display.textContent = `Live allocation for ${formatShiftDisplayDate(today)}`;
  loadShiftEditorForDate(todayStr);
}

// Live employee id lookup shared by the advance + roster forms: the
// directory loaded at startup first, then a fresh /api/employees/ fetch.
async function resolveEmployeeId(name) {
  const key = String(name || '').trim().toLowerCase();
  if (!key) return null;
  if (employeeNameIndex[key]) return employeeNameIndex[key];
  try {
    const rows = await fetchAllApiRows('/api/employees/?page_size=100');
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

  if (!select || !select.value) {
    showToast('Please choose an employee to assign.');
    if (select) select.focus();
    return;
  }

  const employeeId = select.value;
  const option = select.selectedOptions[0];
  const name = option?.dataset.name || option?.textContent || '';
  const roleTag = roleSelect ? roleSelect.value : 'Duty Staff';

  // Save first, then reload the selected date from the database.
  select.selectedIndex = 0;
  if (roleSelect) roleSelect.selectedIndex = 0;
  toggleAddStaffForm(shiftKey, false);
  persistShiftAssignment(shiftKey, employeeId).then((saved) => {
    if (saved) {
      showToast(`Assigned ${name} (${roleTag}) successfully!`);
      loadShiftEditorForDate(document.getElementById('shiftDatePicker')?.value);
      loadMasterShiftCalendar(document.getElementById('shiftDatePicker')?.value);
    } else {
      showToast('Unable to save this roster assignment.', 'error');
    }
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

async function persistShiftAssignment(shiftKey, employeeId) {
  try {
    if (!employeeId) return false;
    const workDate = document.getElementById('shiftDatePicker')?.value || null;
    if (!workDate) return false;
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

function renderShiftEditorSlot(shiftKey, records, employeeById) {
  const usersList = document.getElementById(`shiftUsers-${shiftKey}`);
  const badge = document.getElementById(`shiftBadge-${shiftKey}`);
  if (!usersList) return;
  usersList.innerHTML = '';
  records.filter((record) => record.shift_type === shiftKey).forEach((record) => {
    const employee = employeeById[record.employee] || {};
    const name = `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || employee.email || record.employee || 'Unassigned';
    const initials = name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
    const row = document.createElement('div');
    row.className = 'shift-slot-user-row';
    row.dataset.rosterId = record.id || '';
    row.innerHTML = `
      <div class="shift-slot-user-left">
        <div class="shift-staff-avatar" style="width:28px; height:28px; font-size:11px;">${escapeHtml(initials)}</div>
        <div><strong style="font-size:13px; color:#0f172a;">${escapeHtml(name)}</strong>
        <div style="font-size:11px; color:#64748b;">${escapeHtml(employee.role || '')} &bull; ${escapeHtml(shiftKey)}</div></div>
      </div>
      <button class="btn-remove-staff" title="Remove staff" onclick="removeShiftStaff(this)"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>`;
    usersList.appendChild(row);
  });
  if (!usersList.children.length) {
    usersList.innerHTML = '<div class="shift-empty-placeholder">No staff currently assigned</div>';
  }
  if (badge) {
    badge.className = `penpot-badge ${records.some((record) => record.shift_type === shiftKey) ? 'badge-present' : 'badge-absent'}`;
    badge.textContent = records.some((record) => record.shift_type === shiftKey) ? 'Confirmed' : 'Uncovered';
  }
}

async function loadShiftEditorForDate(workDate) {
  const slots = document.getElementById('shiftSlotsContainer');
  if (!slots || !workDate) return;
  ['morning', 'evening', 'night'].forEach((shiftKey) => {
    const usersList = document.getElementById(`shiftUsers-${shiftKey}`);
    if (usersList) usersList.innerHTML = '<div class="shift-empty-placeholder">Loading assignments...</div>';
  });
  try {
    const [employees, rosters] = await Promise.all([
      fetchAllApiRows('/api/employees/?page_size=100'),
      fetchAllApiRows(`/api/shift-rosters/?page_size=100&work_date=${encodeURIComponent(workDate)}`),
    ]);
    const employeeById = Object.fromEntries(employees.map((employee) => [employee.id, employee]));
    ['morning', 'evening', 'night'].forEach((shiftKey) => renderShiftEditorSlot(shiftKey, rosters, employeeById));
    updateShiftCoverageStatus();
  } catch (_) {
    ['morning', 'evening', 'night'].forEach((shiftKey) => {
      const usersList = document.getElementById(`shiftUsers-${shiftKey}`);
      if (usersList) usersList.innerHTML = '<div class="shift-empty-placeholder">Roster data unavailable</div>';
    });
    showToast('Roster editor data could not be loaded.', 'error');
  }
}


async function removeShiftStaff(btn) {
  const userRow = btn.closest('.shift-slot-user-row');
  const usersList = userRow?.closest('.shift-slot-users-list');
  const slotCard = userRow?.closest('.shift-slot-card');
  const rosterId = userRow?.dataset.rosterId;

  if (!rosterId) return;
  try {
    const res = await apiFetch(`/api/shift-rosters/${rosterId}/`, { method: 'DELETE' });
    if (!res.ok) throw new Error('delete failed');
  } catch (_) {
    showToast('Unable to remove this roster assignment.', 'error');
    return;
  }

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
      const workDate = document.getElementById('shiftDatePicker')?.value;
      loadMasterShiftCalendar(workDate);
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

  const text = String(message || '').trim();
  if (!text) return;
  const duplicate = [...container.querySelectorAll('.toast')].find((toast) => toast.dataset.message === text);
  if (duplicate) {
    duplicate.classList.remove('toast-refresh');
    void duplicate.offsetWidth;
    duplicate.classList.add('toast-refresh');
    return;
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.dataset.message = text;
  if (type === 'error') toast.style.borderLeft = '4px solid #dc2626';
  toast.textContent = text;
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'toast-close';
  close.setAttribute('aria-label', 'Dismiss notification');
  close.textContent = '×';
  close.addEventListener('click', () => dismissToast(toast));
  toast.appendChild(close);
  container.appendChild(toast);

  while (container.children.length > 3) {
    dismissToast(container.firstElementChild, true);
  }

  toast.__timer = setTimeout(() => dismissToast(toast), 3500);
}

function dismissToast(toast, immediate = false) {
  if (!toast || !toast.isConnected) return;
  clearTimeout(toast.__timer);
  if (immediate) {
    toast.remove();
    return;
  }
  toast.style.opacity = '0';
  toast.style.transform = 'translateY(10px)';
  toast.style.transition = 'all 0.2s ease';
  setTimeout(() => toast.remove(), 200);
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
  if (tabKey === 'history') claimsPagerGoto('history', claimsPagerState.history || 1);

  // Update breadcrumb trail for Claims subtab
  const breadcrumbTrail = document.getElementById('breadcrumbTrail');
  if (breadcrumbTrail) {
    const claimsTabNames = {
      'pending': 'Pending Claims',
      'history': 'Claims History',
      'advance': 'Advance Pay Requests'
    };
    const activeLabel = claimsTabNames[tabKey] || 'Pending Claims';
    breadcrumbTrail.innerHTML = `<span class="bc-root">Claims</span> <span class="bc-slash">/</span> <span class="bc-page">${activeLabel}</span>`;
  }
}

async function loadClaimsSummary() {
  try {
    const [claims, advances] = await Promise.all([
      fetchAllApiRows('/api/expense-claims/?page_size=100'),
      fetchAllApiRows('/api/advances/?page_size=100'),
    ]);
    const count = (rows, status) => rows.filter((row) => row.status === status).length;
    const year = new Date().getFullYear();
    const ytdClaims = claims.filter((claim) => String(claim.created_at || '').slice(0, 4) === String(year));
    const approvedClaims = ytdClaims.filter((claim) => claim.status === 'Approved');
    const rejectedClaims = ytdClaims.filter((claim) => claim.status === 'Rejected');
    const settledClaims = [...approvedClaims, ...rejectedClaims];
    const settledAmount = settledClaims.reduce((total, claim) => total + Number(claim.amount || 0), 0);
    const processingDays = settledClaims
      .map((claim) => (new Date(claim.updated_at) - new Date(claim.created_at)) / 86400000)
      .filter((days) => Number.isFinite(days) && days >= 0);
    const averageDays = processingDays.length
      ? processingDays.reduce((total, days) => total + days, 0) / processingDays.length
      : null;
    const pending = document.getElementById('claimsPendingCount');
    const approved = document.getElementById('claimsApprovedCount');
    const rejected = document.getElementById('claimsRejectedCount');
    const pendingAdvances = document.getElementById('advancesPendingCount');
    if (pending) pending.textContent = count(claims, 'Pending');
    if (approved) approved.textContent = count(claims, 'Approved');
    if (rejected) rejected.textContent = count(claims, 'Rejected');
    if (pendingAdvances) pendingAdvances.textContent = count(advances, 'Pending');
    const settledTarget = document.getElementById('claimsHistorySettledCount');
    const settledAmountTarget = document.getElementById('claimsHistorySettledAmount');
    const approvedTarget = document.getElementById('claimsHistoryApprovedCount');
    const rejectedTarget = document.getElementById('claimsHistoryRejectedCount');
    const approvedRateTarget = document.getElementById('claimsHistoryApprovedRate');
    const rejectedRateTarget = document.getElementById('claimsHistoryRejectedRate');
    const speedTarget = document.getElementById('claimsHistorySpeed');
    const speedSubtext = document.getElementById('claimsHistorySpeedSubtext');
    const settledCount = settledClaims.length;
    if (settledTarget) settledTarget.textContent = settledCount;
    if (settledAmountTarget) settledAmountTarget.textContent = `$${settledAmount.toFixed(2)} total`;
    if (approvedTarget) approvedTarget.textContent = approvedClaims.length;
    if (rejectedTarget) rejectedTarget.textContent = rejectedClaims.length;
    if (approvedRateTarget) approvedRateTarget.textContent = `${settledCount ? ((approvedClaims.length / settledCount) * 100).toFixed(1) : '0'}% of settled`;
    if (rejectedRateTarget) rejectedRateTarget.textContent = `${settledCount ? ((rejectedClaims.length / settledCount) * 100).toFixed(1) : '0'}% of settled`;
    if (speedTarget) speedTarget.textContent = averageDays === null ? '—' : `${averageDays.toFixed(1)}d`;
    if (speedSubtext) speedSubtext.textContent = averageDays === null ? 'Awaiting processed claims' : `${processingDays.length} processed claim${processingDays.length === 1 ? '' : 's'}`;
  } catch (_) {
    // The live tables show their own unavailable state.
  }
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
  loadClaimsSummary();
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
  loadClaimsSummary();
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
// Live pagers fetch each page from the API and render an explicit empty/error state.
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

function updatePagerControls(pagerName, page, total, pageSize) {
  const bar = document.querySelector(`[data-pager="${pagerName}"]`);
  if (!bar) return;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageButtons = Array.from(bar.querySelectorAll('[data-pagenum]'));
  const firstPage = Math.max(1, Math.min(page - 1, totalPages - pageButtons.length + 1));
  const pageActions = {
    'claims-pending': (number) => `claimsPagerGoto('pending', ${number})`,
    'claims-history': (number) => `claimsPagerGoto('history', ${number})`,
    advances: (number) => `advancesPagerGoto(${number})`,
    audit: (number) => `auditPagerGoto(${number})`,
  };
  pageButtons.forEach((button, index) => {
    const pageNumber = firstPage + index;
    button.dataset.pagenum = String(pageNumber);
    button.textContent = String(pageNumber);
    button.hidden = pageNumber > totalPages;
    if (pageActions[pagerName]) button.setAttribute('onclick', pageActions[pagerName](pageNumber));
  });
  const previous = bar.querySelector('[data-page-prev]');
  const next = bar.querySelector('[data-page-next]');
  if (previous) previous.disabled = page <= 1;
  if (next) next.disabled = page >= totalPages;
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

async function fetchAllApiRows(path) {
  const rows = [];
  let nextPath = path;
  const seenPaths = new Set();
  while (nextPath) {
    if (seenPaths.has(nextPath)) throw new Error('The API returned a repeated pagination URL.');
    seenPaths.add(nextPath);
    const response = await apiFetch(nextPath, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    if (!response.ok) throw new Error('Records could not be loaded.');
    const payload = await response.json();
    if (Array.isArray(payload)) {
      rows.push(...payload);
      break;
    }
    rows.push(...(Array.isArray(payload.results) ? payload.results : []));
    if (!payload.next) break;
    const next = new URL(payload.next, window.location.origin);
    if (next.origin !== window.location.origin || !next.pathname.startsWith('/api/')) {
      throw new Error('The API returned an unsafe pagination URL.');
    }
    nextPath = `${next.pathname}${next.search}`;
  }
  return rows;
}

async function claimsPagerGoto(which, page) {
  if (page < 1) return;
  const bodyId = which === 'pending' ? 'pendingClaimsTableBody' : 'historyClaimsTableBody';
  const infoId = which === 'pending' ? 'pendingPagerInfo' : 'historyPagerInfo';
  const pagerName = which === 'pending' ? 'claims-pending' : 'claims-history';
  const body = document.getElementById(bodyId);
  if (!body) return;
  body.innerHTML = '<tr><td colspan="7">Loading claims…</td></tr>';
  try {
    const statusFilter = which === 'pending' ? 'Pending' : 'Approved,Rejected';
    const res = await apiFetch(`/api/expense-claims/?status=${statusFilter}&page=${page}&page_size=${CLAIMS_PAGE_SIZE}`);
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
    const totalPages = Math.max(1, Math.ceil(total / CLAIMS_PAGE_SIZE));
    if (info) info.textContent = total
      ? `Page ${page} of ${totalPages} · ${total} ${which === 'pending' ? 'pending' : 'processed'} claims`
      : `No ${which === 'pending' ? 'pending claims' : 'claim history'} yet`;
    claimsPagerState[which] = page;
    updatePagerControls(pagerName, page, total, CLAIMS_PAGE_SIZE);
    markPagerActive(pagerName, page);
    if (which === 'pending' && typeof updateBatchApproveCount === 'function') updateBatchApproveCount();
  } catch (e) {
    body.innerHTML = '<tr><td colspan="7">Claims data is unavailable.</td></tr>';
    showToast('Claims data is unavailable.', 'error');
  }
}

function buildClaimRow(c, which, names) {
  const id = String(c.id || '');
  const who = String(names[c.employee] || c.employee || 'Unknown');
  const statusCls = String(c.status || 'Pending').toLowerCase();
  const tr = document.createElement('tr');
  tr.id = `claim-row-${id}`;
  tr.setAttribute('data-live', 'true');
  tr.dataset.claimId = id;
  tr.dataset.employee = who;
  tr.dataset.category = String(c.category || 'General Expense');
  tr.dataset.createdAt = String(c.created_at || '');
  tr.dataset.title = String(c.title || '');
  tr.dataset.amount = String(c.amount || '0');
  tr.dataset.status = String(c.status || 'Pending');
  const pill = `<span class="claims-status-pill ${statusCls}" id="status-${id}">${escapeHtml(String(c.status || 'Pending'))}</span>`;
  const actions = statusCls === 'pending' ?
    `<div class="claims-actions-cell" id="actions-${id}">` +
    `<button class="btn-claim-approve" onclick="handleClaimAction('${escapeHtml(id)}', 'Approve')">Approve</button>` +
    `<button class="btn-claim-reject" onclick="handleClaimAction('${escapeHtml(id)}', 'Reject')">Reject</button>` +
    `</div>` : '<span style="font-size:12px; color:#64748b; font-weight:600;">Processed</span>';
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

async function exportClaimHistory() {
  const rows = [['Claim ID', 'Employee', 'Category', 'Submitted', 'Expense Details', 'Amount', 'Status']];
  let claims;
  let names = {};
  try {
    [claims, names] = await Promise.all([
      fetchAllApiRows('/api/expense-claims/?status=Approved,Rejected&page_size=100'),
      liveEmployeeNames().catch(() => ({})),
    ]);
  } catch (error) {
    if (error.message !== 'auth') showToast(error.message || 'Claim history could not be loaded.', 'error');
    return;
  }
  claims.forEach((claim) => {
    rows.push([
      String(claim.id || ''),
      String(names[claim.employee] || claim.employee || 'Unknown'),
      String(claim.category || 'General Expense'),
      fmtClaimDate(claim.created_at || ''),
      String(claim.title || ''),
      String(claim.amount || '0'),
      String(claim.status || 'Processed'),
    ]);
  });

  if (rows.length === 1) {
    showToast('No live claim history is available to export.', 'error');
    return;
  }
  downloadCsv(`kumon_ems_claim_history_${new Date().toISOString().slice(0, 10)}.csv`, rows);
  showToast(`Exported ${rows.length - 1} claim history record${rows.length === 2 ? '' : 's'}.`);
}

// Advances pager fetches /api/advances/ and renders backend records.
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
  const actions = String(a.status || 'Pending').toLowerCase() === 'pending' ?
    `<div class="claims-actions-cell" id="actions-${id}">` +
    `<button class="btn-claim-approve" onclick="handleAdvanceAction('${escapeHtml(id)}', 'Approved')">Approve</button>` +
    `<button class="btn-claim-reject" onclick="handleAdvanceAction('${escapeHtml(id)}', 'Rejected')">Reject</button>` +
    `</div>` : '<span style="font-size:12px; color:#64748b; font-weight:600;">Processed</span>';
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

async function handleAdvanceAction(id, status) {
  try {
    const res = await apiFetch(`/api/advances/${encodeURIComponent(id)}/`, {
      method: 'PATCH',
      body: JSON.stringify({ decision: status }),
    });
    if (!res.ok) throw new Error('advance decision failed');
    await advancesPagerGoto(advancesPagerPage);
    loadClaimsSummary();
    showToast(`Salary advance ${status.toLowerCase()}.`);
  } catch (_) {
    showToast('Salary advance status could not be saved.', 'error');
  }
}

async function advancesPagerGoto(page) {
  if (page < 1) return;
  const body = document.getElementById('advanceClaimsTableBody');
  if (!body) return;
  body.innerHTML = '<tr><td colspan="7">Loading advances…</td></tr>';
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
    const totalPages = Math.max(1, Math.ceil(total / ADVANCES_PAGE_SIZE));
    if (info) info.textContent = total
      ? `Page ${page} of ${totalPages} · ${total} advance applications`
      : 'No advance applications yet';
    advancesPagerPage = page;
    updatePagerControls('advances', page, total, ADVANCES_PAGE_SIZE);
    markPagerActive('advances', page);
  } catch (e) {
    body.innerHTML = '<tr><td colspan="7">Advance data is unavailable.</td></tr>';
    showToast('Advance data is unavailable.', 'error');
  }
}


// Advance Pay Modal
function openAdvanceModal() {
  const modal = document.getElementById('advanceModal');
  if (modal) modal.classList.add('active');
  loadEmployeeOptions('advanceApplicant');
}

function closeAdvanceModal() {
  const modal = document.getElementById('advanceModal');
  if (modal) modal.classList.remove('active');
}

// Shared refresh path keeps the register and its pagination in sync.
function loadAdvancesView() {
  return advancesPagerGoto(advancesPagerPage || 1);
}

async function handleRequestAdvance(e) {
  e.preventDefault();
  const form = e.target;
  const applicant = document.getElementById('advanceApplicant');
  const amount = document.getElementById('advanceAmount')?.value || '';
  const terms = document.getElementById('advanceTerms')?.value || 'Next Payroll';
  const purpose = document.getElementById('advancePurpose')?.value.trim() || '';
  if (!(Number(amount) > 0)) {
    showToast('Requested amount must be greater than zero.', 'error');
    return;
  }
  try {
    const res = await apiFetch('/api/advances/', {
      method: 'POST',
      body: JSON.stringify({
        employee: applicant?.value || undefined,
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

function formatLeaveDate(value) {
  if (!value) return '-';
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function leaveDuration(start, end) {
  const from = new Date(`${start}T00:00:00`);
  const to = new Date(`${end}T00:00:00`);
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return '-';
  const days = Math.floor((to - from) / 86400000) + 1;
  return `${days} ${days === 1 ? 'Calendar Day' : 'Calendar Days'}`;
}

async function loadLeaveRegister() {
  const body = document.getElementById('leaveRegisterTableBody');
  if (!body) return;
  try {
    const rows = await fetchAllApiRows('/api/leaves/?page_size=100');
    const today = localDateIso();
    const pendingCount = rows.filter((leave) => leave.status === 'Pending').length;
    const approvedCount = rows.filter((leave) => leave.status === 'Approved').length;
    const onLeaveToday = new Set(rows
      .filter((leave) => leave.status === 'Approved' && leave.start_date <= today && leave.end_date >= today)
      .map((leave) => leave.employee)
      .filter(Boolean)).size;
    const pendingTarget = document.getElementById('leavePendingCount');
    const approvedTarget = document.getElementById('leaveApprovedCount');
    const todayTarget = document.getElementById('leaveTodayCount');
    if (pendingTarget) pendingTarget.textContent = pendingCount;
    if (approvedTarget) approvedTarget.textContent = approvedCount;
    if (todayTarget) todayTarget.textContent = onLeaveToday;
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6">No leave applications yet.</td></tr>';
      return;
    }
    rows.forEach((leave) => {
      const status = String(leave.status || 'Pending');
      const statusClass = status.toLowerCase() === 'approved'
        ? 'badge-accepted'
        : status.toLowerCase() === 'rejected' ? 'badge-rejected' : 'badge-pending';
      const type = leave.leave_type || 'Personal';
      const row = document.createElement('tr');
      const actions = status.toLowerCase() === 'pending'
        ? `<div class="claims-actions-cell"><button class="btn-claim-approve" onclick="handleLeaveAction('${escapeHtml(leave.id)}', 'Approved')">Approve</button><button class="btn-claim-reject" onclick="handleLeaveAction('${escapeHtml(leave.id)}', 'Rejected')">Reject</button></div>`
        : '<span style="font-size:12px; color:#64748b; font-weight:600;">Processed</span>';
      row.innerHTML =
        `<td><div class="bold-title">${escapeHtml(leave.employee_name || 'Unknown employee')}</div>` +
        `<div class="sub-role">${escapeHtml(leave.employee_role || '')}` +
        `${leave.employee_department ? ` • ${escapeHtml(leave.employee_department)}` : ''}</div></td>` +
        `<td><span class="penpot-leave-pill pill-blue">${escapeHtml(type)}</span></td>` +
        `<td><div class="bold-title">${leaveDuration(leave.start_date, leave.end_date)}</div>` +
        `<div class="sub-role">${formatLeaveDate(leave.start_date)} - ${formatLeaveDate(leave.end_date)}</div></td>` +
        `<td>${formatLeaveDate((leave.created_at || '').slice(0, 10))}</td>` +
        `<td><span class="penpot-badge ${statusClass}">● ${escapeHtml(status)}</span></td>` +
        `<td>${actions}</td>`;
      body.appendChild(row);
    });
  } catch (error) {
    body.innerHTML = '<tr><td colspan="6">Unable to load leave applications.</td></tr>';
  }
}

async function handleLeaveAction(id, status) {
  try {
    const res = await apiFetch(`/api/leaves/${encodeURIComponent(id)}/`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error('leave decision failed');
    await loadLeaveRegister();
    loadDashboardSummary();
    showToast(`Leave request ${status.toLowerCase()}.`);
  } catch (_) {
    showToast('Leave request status could not be saved.', 'error');
  }
}

// Leave Application Modal
function openLeaveModal() {
  const modal = document.getElementById('leaveModal');
  if (modal) modal.classList.add('active');
  loadEmployeeOptions('leaveApplicant');
}

function closeLeaveModal() {
  const modal = document.getElementById('leaveModal');
  if (modal) modal.classList.remove('active');
}

function handleApplyLeave(e) {
  e.preventDefault();
  const form = e.target;
  const employeeId = document.getElementById('leaveApplicant')?.value || '';
  apiFetch('/api/leaves/', {
    method: 'POST',
    body: JSON.stringify({
      employee: employeeId || undefined,
      leave_type: document.getElementById('leaveType')?.value || 'Personal',
      start_date: document.getElementById('leaveStartDate')?.value || null,
      end_date: document.getElementById('leaveEndDate')?.value || null,
      reason: document.getElementById('leaveReason')?.value.trim() || '',
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
      loadLeaveRegister();
      loadDashboardSummary();
    })
    .catch(() => showToast('Unable to file leave. Try again later.', 'error'));
}


// ==========================================================================
// Messages & Channels Handlers
// ==========================================================================
let activeConversationKey = 'announcements';
let messagesLoadVersion = 0;


function filterInboxes(input) {
  const q = input.value.toLowerCase();
  const tiles = document.querySelectorAll('#inboxConversationsList .inbox-user-tile');
  tiles.forEach(tile => {
    const text = tile.textContent.toLowerCase();
    tile.style.display = text.includes(q) ? 'flex' : 'none';
  });
}

async function loadEmployeeInbox() {
  const list = document.getElementById('inboxConversationsList');
  if (!list) return;
  const previousKey = activeConversationKey;
  try {
    const employees = await fetchAllApiRows('/api/employees/?page_size=100&is_active=true');
    list.innerHTML = '';
    if (!employees.length) {
      list.innerHTML = '<div class="card-sub">No active employees in the roster.</div>';
      activeConversationKey = 'announcements';
      const channel = document.querySelector('.channel-list-item');
      if (channel) selectChannel(channel, 'announcements', false);
      else loadMessagesForConversation('announcements');
      return;
    }
    const avatarClasses = ['avatar-blue', 'avatar-yellow', 'avatar-green', 'avatar-purple', 'avatar-slate'];
    employees.forEach((employee, index) => {
      const name = `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || employee.email || 'Employee';
      const initials = name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
      const role = employee.role || 'Employee';
      const tile = document.createElement('div');
      const employeeKey = String(employee.id);
      tile.className = `inbox-user-tile${employeeKey === previousKey ? ' active' : ''}`;
      tile.innerHTML =
        `<div class="avatar-circle-sm ${avatarClasses[index % avatarClasses.length]}">${escapeHtml(initials)}</div>` +
        `<div class="inbox-tile-content"><div class="inbox-tile-top"><strong>${escapeHtml(name)}</strong>` +
        `<span class="inbox-timestamp">Roster</span></div><span class="inbox-snippet">${escapeHtml(role)}</span></div>`;
      tile.addEventListener('click', () => selectInboxUser(tile, name, initials, role, employeeKey));
      list.appendChild(tile);
      if (employeeKey === previousKey) {
        selectInboxUser(tile, name, initials, role, employeeKey, false);
      }
    });
    if (!employees.some((employee) => String(employee.id) === previousKey)) {
      activeConversationKey = 'announcements';
      const channel = document.querySelector('.channel-list-item');
      if (channel) selectChannel(channel, 'announcements', false);
      else loadMessagesForConversation('announcements');
    }
  } catch (_) {
    list.innerHTML = '<div class="card-sub">Employee conversations are unavailable.</div>';
    activeConversationKey = 'announcements';
    const channel = document.querySelector('.channel-list-item');
    if (channel) selectChannel(channel, 'announcements', false);
    else loadMessagesForConversation('announcements');
    showToast('Employee roster could not be loaded for Messages.', 'error');
  }
}

function selectChannel(elem, channelKey, notify = true) {
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
  if (notify) showToast('Switched to # Company Announcements channel.');
}

// Route profile messages into the in-app conversation view.
function messageInApp(fullName) {
  switchView('messages');
  const tiles = document.querySelectorAll('.inbox-user-tile');
  const hit = Array.from(tiles).find((t) =>
    (t.textContent || '').toLowerCase().includes((fullName || '').toLowerCase().split(' ')[0])
  );
  if (hit) hit.click();
  else showToast('No conversation is available for this employee yet.', 'info');
}
function selectInboxUser(elem, userName, initials, userRole, key, notify = true) {
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
  if (status) status.textContent = `● ${userRole}`;
  if (input) input.placeholder = `Type a message to ${userName}...`;
  loadMessagesForConversation(key);
  if (notify) showToast(`Active chat: ${userName}`);
}

async function loadMessagesForConversation(conversationKey) {
  const stream = document.getElementById('chatStreamMessages');
  if (!stream) return;

  const loadVersion = ++messagesLoadVersion;
  stream.innerHTML = '<div class="chat-loading-state">Loading messages...</div>';
  try {
    const params = new URLSearchParams({ conversation: conversationKey, page_size: '100' });
    const search = document.getElementById('conversationSearchInput')?.value.trim();
    if (search) params.set('search', search);
    const messages = await fetchAllApiRows(`/api/messages/?${params.toString()}`);
    if (loadVersion !== messagesLoadVersion) return;
    if (conversationKey === 'announcements') {
      const preview = document.querySelector('.channel-last-msg');
      if (preview) {
        const latest = messages[messages.length - 1];
        preview.textContent = latest?.text || (latest?.attachment_url ? 'Attachment' : 'No messages yet');
      }
    }
    stream.innerHTML = '';
    if (!messages.length) {
      stream.innerHTML = '<div class="chat-loading-state">No messages in this conversation yet.</div>';
    }
    messages.forEach(message => appendPersistedMessage(stream, message));
    stream.scrollTop = stream.scrollHeight;
  } catch (error) {
    if (loadVersion !== messagesLoadVersion) return;
    stream.innerHTML = '<div class="chat-loading-state">Messages are unavailable. Check your connection and try again.</div>';
    showToast('Messages could not be loaded.', 'error');
  }
}

function toggleConversationSearch() {
  const form = document.getElementById('conversationSearch');
  const trigger = document.querySelector('.chat-header-actions button[aria-controls="conversationSearch"]');
  if (!form) return;
  form.hidden = !form.hidden;
  trigger?.setAttribute('aria-expanded', String(!form.hidden));
  if (!form.hidden) document.getElementById('conversationSearchInput')?.focus();
}

function searchConversationMessages(event) {
  event.preventDefault();
  loadMessagesForConversation(activeConversationKey);
}

function clearConversationSearch() {
  const input = document.getElementById('conversationSearchInput');
  if (input) input.value = '';
  loadMessagesForConversation(activeConversationKey);
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
// Settings view (T9+T15): profile, notifications/display, company (staff-only)
// GET/PATCH /api/settings/me/, POST /api/settings/password/,
// GET/PATCH /api/settings/site/ (staff). a11y enforced via --fs-scale +
// html[data-contrast]/html[data-motion] (see main.css tail).
// ==========================================================================
const SETTINGS_FONT_SCALES = ['87.5', '100', '112.5', '125'];
let settingsCache = null;
let settingsIsStaff = false;
let settingsConfirmAction = null;

function applySettingsA11y(a11y) {
  const a = a11y || {};
  let scale = String(a.font_scale != null ? a.font_scale : '100');
  if (!SETTINGS_FONT_SCALES.includes(scale)) scale = '100';
  // html font-size scales the whole rem-based layout.
  document.documentElement.style.setProperty('--fs-scale', scale + '%');
  document.documentElement.dataset.contrast = a.high_contrast ? 'high' : 'normal';
  document.documentElement.dataset.motion = a.reduce_motion ? 'reduced' : 'full';
}

// a11y apply on every load: fetch settings/me and set --fs-scale + datasets.
// Falls back to logged-out-safe defaults when the API is unreachable.
async function applySettingsA11yOnLoad() {
  try {
    const res = await apiFetch('/api/settings/me/');
    if (!res.ok) throw new Error('settings unreachable');
    const data = await res.json();
    applySettingsA11y(data.a11y || {});
  } catch (_) {
    applySettingsA11y({ font_scale: 100, high_contrast: false, reduce_motion: false });
  }
}

function settingsSwitchTab(which) {
  const panes = { profile: 'settingsPaneProfile', notif: 'settingsPaneNotif', company: 'settingsPaneCompany' };
  const tabs = { profile: 'settingsTabProfile', notif: 'settingsTabNotif', company: 'settingsTabCompany' };
  Object.entries(panes).forEach(([key, id]) => {
    const pane = document.getElementById(id);
    if (pane && !(key === 'company' && !settingsIsStaff)) {
      pane.style.display = key === which ? 'block' : 'none';
    }
  });
  Object.entries(tabs).forEach(([key, id]) => {
    const tab = document.getElementById(id);
    if (tab) tab.classList.toggle('active', key === which);
  });
}

function renderAccountProfile(data) {
  const p = data.profile || {};
  const first = p.first_name || '';
  const last = p.last_name || '';
  const name = [first, last].filter(Boolean).join(' ') || p.username || 'Account holder';
  const initials = [first[0], last[0]].filter(Boolean).join('') || name.slice(0, 2);
  const role = p.role || 'Account holder';
  const dept = p.department_name || 'Not assigned';
  const managed = Array.isArray(p.managed_departments) ? p.managed_departments : [];
  const put = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value || '—'; };
  put('accountDisplayName', name);
  put('accountRoleLine', `${role}${p.department_name ? ` · ${p.department_name}` : ''}`);
  put('accountEmailLine', p.email || 'No work email');
  put('accountDepartmentLine', dept);
  put('accountUsernameLine', p.username || '—');
  put('accountManagedLine', managed.join(', ') || 'None assigned');
  put('accountAvatar', initials.toUpperCase());
  const managedRow = document.getElementById('accountManagedRow');
  if (managedRow) managedRow.hidden = !managed.length;
  const kicker = document.getElementById('accountProfileKicker');
  if (kicker) kicker.textContent = managed.length ? 'MANAGER PROFILE' : 'ACCOUNT PROFILE';
  const set = (id, value) => { const el = document.getElementById(id); if (el) el.value = value || ''; };
  set('accountFirstName', first);
  set('accountLastName', last);
  set('accountEmail', p.email);
  set('accountRole', role);
  setAccountTwoFactorState(!!data.two_factor_enabled);
}

async function loadAccountProfile() {
  try {
    const res = await apiFetch('/api/settings/me/');
    if (!res.ok) throw new Error('Account profile could not be loaded.');
    const data = await res.json();
    renderAccountProfile(data);
  } catch (error) {
    const status = document.getElementById('accountProfileStatus');
    if (status) status.textContent = error.message || 'Account profile could not be loaded.';
  }
}

async function saveAccountProfile() {
  const profile = {
    first_name: document.getElementById('accountFirstName')?.value.trim() || '',
    last_name: document.getElementById('accountLastName')?.value.trim() || '',
    email: document.getElementById('accountEmail')?.value.trim() || '',
  };
  const status = document.getElementById('accountProfileStatus');
  if (status) status.textContent = '';
  try {
    const res = await apiFetch('/api/settings/me/', { method: 'PATCH', body: JSON.stringify({ profile }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.email?.join?.(' ') || 'Profile could not be saved.');
    renderAccountProfile(data);
    if (status) status.textContent = 'Profile saved.';
  } catch (error) {
    if (status) status.textContent = error.message || 'Profile could not be saved.';
  }
}

function setAccountTwoFactorState(enabled) {
  const badge = document.getElementById('accountMfaBadge');
  const on = document.getElementById('accountMfaEnabled');
  const off = document.getElementById('accountMfaDisabled');
  const setup = document.getElementById('accountMfaSetup');
  if (badge) {
    badge.textContent = enabled ? 'PROTECTED' : 'NOT ENABLED';
    badge.classList.toggle('is-enabled', enabled);
  }
  if (on) on.hidden = !enabled;
  if (off) off.hidden = enabled;
  if (setup && enabled) setup.hidden = true;
}

async function startAccountTwoFactorSetup() {
  const password = document.getElementById('accountMfaSetupPassword')?.value || '';
  if (!password) { showToast('Enter your current password first.', 'error'); return; }
  try {
    const res = await apiFetch('/api/settings/2fa/setup/', { method: 'POST', body: JSON.stringify({ current_password: password }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Authenticator setup could not start.');
    const secret = document.getElementById('accountMfaSecret');
    const setup = document.getElementById('accountMfaSetup');
    if (secret) secret.textContent = data.secret;
    if (setup) setup.hidden = false;
    document.getElementById('accountMfaConfirmCode')?.focus();
  } catch (error) { showToast(error.message, 'error'); }
}

async function confirmAccountTwoFactorSetup() {
  const password = document.getElementById('accountMfaSetupPassword')?.value || '';
  const code = document.getElementById('accountMfaConfirmCode')?.value || '';
  try {
    const res = await apiFetch('/api/settings/2fa/confirm/', { method: 'POST', body: JSON.stringify({ current_password: password, code }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'That code could not be verified.');
    const list = document.getElementById('accountRecoveryCodeList');
    const panel = document.getElementById('accountRecoveryCodes');
    if (list) list.textContent = (data.recovery_codes || []).join('\n');
    if (panel) panel.hidden = false;
    const pwd = document.getElementById('accountMfaSetupPassword'); if (pwd) pwd.value = '';
    const codeInput = document.getElementById('accountMfaConfirmCode'); if (codeInput) codeInput.value = '';
    setAccountTwoFactorState(true);
    const status = document.getElementById('accountMfaStatus'); if (status) status.textContent = 'Two-factor authentication is on.';
  } catch (error) { showToast(error.message, 'error'); }
}

async function disableAccountTwoFactor() {
  if (!window.confirm('Turn off two-factor authentication for this account?')) return;
  const current_password = document.getElementById('accountMfaDisablePassword')?.value || '';
  const code = document.getElementById('accountMfaDisableCode')?.value || '';
  try {
    const res = await apiFetch('/api/settings/2fa/disable/', { method: 'POST', body: JSON.stringify({ current_password, code }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Two-factor authentication could not be turned off.');
    document.getElementById('accountMfaDisablePassword').value = '';
    document.getElementById('accountMfaDisableCode').value = '';
    document.getElementById('accountRecoveryCodes').hidden = true;
    setAccountTwoFactorState(false);
    const status = document.getElementById('accountMfaStatus'); if (status) status.textContent = 'Two-factor authentication is off.';
  } catch (error) { showToast(error.message, 'error'); }
}

async function copyRecoveryCodes(elementId) {
  const value = document.getElementById(elementId)?.textContent || '';
  try {
    await navigator.clipboard.writeText(value);
    showToast('Recovery codes copied. Store them somewhere private.');
  } catch (_) { showToast('Copy is unavailable here. Select and copy the recovery codes.', 'error'); }
}

function settingsRevealStaff() {
  document.querySelectorAll('#view-settings [data-staff-only]').forEach((el) => {
    if (settingsIsStaff) el.removeAttribute('hidden');
    else el.setAttribute('hidden', '');
  });
}

async function loadSettingsView() {
  try {
    const res = await apiFetch('/api/settings/me/');
    if (!res.ok) throw new Error('load failed');
    const data = await res.json();
    settingsCache = data;
    renderSettingsForm(data);
    // Staff probe: site settings GET is staff-only; 403/404 keeps company hidden.
    try {
      const site = await apiFetch('/api/settings/site/');
      if (site.ok) {
        settingsIsStaff = true;
        renderSettingsSite(await site.json());
      } else {
        settingsIsStaff = false;
      }
    } catch (_) { settingsIsStaff = false; }
    settingsRevealStaff();
    applySettingsA11y(data.a11y || {});
  } catch (e) {
    showToast('Settings are unavailable. Try again later.', 'error');
    const errNote = document.getElementById('settingsLoadError');
    if (errNote) errNote.style.display = 'block';
    document.querySelectorAll('#view-settings .btn-navy-cta').forEach((b) => {
      b.disabled = true;
    });
  }
}

function renderSettingsForm(data) {
  const p = data.profile || {};
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val != null ? val : ''; };
  set('setFirstName', p.first_name);
  set('setLastName', p.last_name);
  set('setEmail', p.email);
  set('setRole', p.role);
  const muted = Array.isArray(data.muted_kinds) ? data.muted_kinds : [];
  const ml = document.getElementById('setMuteLeave'); if (ml) ml.checked = muted.includes('leave');
  const ms = document.getElementById('setMuteShift'); if (ms) ms.checked = muted.includes('shift');
  const mp = document.getElementById('setMutePayroll'); if (mp) mp.checked = muted.includes('payroll');
  const ps = document.getElementById('setPageSize'); if (ps) ps.value = String(data.page_size || 10);
  const a = data.a11y || {};
  const fs = document.getElementById('setFontScale');
  if (fs) fs.value = String(a.font_scale != null ? a.font_scale : '100');
  const hc = document.getElementById('setHighContrast'); if (hc) hc.checked = !!a.high_contrast;
  const rm = document.getElementById('setReduceMotion'); if (rm) rm.checked = !!a.reduce_motion;
}

function renderSettingsSite(site) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val != null ? val : ''; };
  const setChecked = (id, val) => { const el = document.getElementById(id); if (el) el.checked = String(val).toLowerCase() === 'true'; };
  set('setOtMin', site.overtime_min_hours);
  set('setOtMax', site.overtime_max_hours);
  set('setPurgeDays', site.purge_retention_days);
  set('setUploadCap', site.onboarding_max_mb);
  setChecked('setLeaveBackdated', site.leave_restrict_backdated);
  set('setLeaveAutoDays', site.leave_auto_allocate_days);
  setChecked('setShiftDouble', site.shift_allow_double_booking);
  setChecked('setMobileCheckin', site.mobile_checkin_enabled != null ? site.mobile_checkin_enabled : true);
  const ro = document.getElementById('setReadOnlyNet');
  if (ro) {
    ro.textContent =
      `throttle anon ${site.throttle_anon || '—'} · user ${site.throttle_user || '—'} · CORS ${(site.cors_origins || []).join(', ') || '—'}`;
  }
}

function openSettingsConfirm(title, text, action) {
  const modal = document.getElementById('settingsConfirmModal');
  const t = document.getElementById('settingsConfirmTitle');
  const b = document.getElementById('settingsConfirmText');
  const ok = document.getElementById('settingsConfirmOk');
  if (!modal || !ok) { if (typeof action === 'function') action(); return; }
  if (t) t.textContent = title;
  if (b) b.textContent = text;
  settingsConfirmAction = action;
  ok.onclick = async () => {
    closeSettingsConfirm();
    if (typeof settingsConfirmAction === 'function') await settingsConfirmAction();
  };
  modal.classList.add('active');
}

function closeSettingsConfirm() {
  const modal = document.getElementById('settingsConfirmModal');
  if (modal) modal.classList.remove('active');
  settingsConfirmAction = null;
}

function collectMutedKinds() {
  const kinds = [];
  if (document.getElementById('setMuteLeave')?.checked) kinds.push('leave');
  if (document.getElementById('setMuteShift')?.checked) kinds.push('shift');
  if (document.getElementById('setMutePayroll')?.checked) kinds.push('payroll');
  return kinds;
}

async function saveSettingsProfile() {
  const profile = {
    first_name: document.getElementById('setFirstName')?.value.trim() || '',
    last_name: document.getElementById('setLastName')?.value.trim() || '',
    email: document.getElementById('setEmail')?.value.trim() || '',
  };
  openSettingsConfirm('Save profile?', 'Your employee name and email will be updated.', async () => {
    try {
      const res = await apiFetch('/api/settings/me/', { method: 'PATCH', body: JSON.stringify({ profile }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.error === 'string' ? data.error : (data.email && data.email.join(' ')) || 'save failed');
      settingsCache = { ...(settingsCache || {}), profile: data.profile || profile };
      renderSettingsForm({ ...(settingsCache || {}), profile: settingsCache.profile });
      showToast('Profile saved.');
    } catch (error) {
      showToast(error.message || 'Profile save failed.', 'error');
    }
  });
}

async function saveSettingsPassword() {
  const oldPw = document.getElementById('setOldPassword')?.value || '';
  const nw = document.getElementById('setNewPassword')?.value || '';
  const nw2 = document.getElementById('setNewPassword2')?.value || '';
  if (!oldPw || !nw) { showToast('Enter your current and a new password.', 'error'); return; }
  if (nw !== nw2) { showToast('New passwords do not match.', 'error'); return; }
  if (nw.length < 8) { showToast('New password must be at least 8 characters.', 'error'); return; }
  openSettingsConfirm('Change password?', 'You will stay signed in here; other sessions sign out.', async () => {
    try {
      const res = await apiFetch('/api/settings/password/', {
        method: 'POST',
        body: JSON.stringify({ old_password: oldPw, new_password: nw }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.error === 'string' ? data.error : 'password change failed');
      ['setOldPassword', 'setNewPassword', 'setNewPassword2'].forEach((id) => {
        const el = document.getElementById(id); if (el) el.value = '';
      });
      showToast(data.message || 'Password changed.');
    } catch (error) {
      showToast(error.message || 'Password change failed.', 'error');
    }
  });
}

async function saveSettingsPrefs() {
  const a11y = {
    font_scale: parseFloat(document.getElementById('setFontScale')?.value || '100'),
    high_contrast: !!document.getElementById('setHighContrast')?.checked,
    reduce_motion: !!document.getElementById('setReduceMotion')?.checked,
  };
  const payload = { page_size: parseInt(document.getElementById('setPageSize')?.value || '10', 10), muted_kinds: collectMutedKinds(), a11y };
  try {
    const res = await apiFetch('/api/settings/me/', { method: 'PATCH', body: JSON.stringify(payload) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.error === 'string' ? data.error : 'save failed');
    settingsCache = { ...(settingsCache || {}), ...data };
    applySettingsA11y(data.a11y || a11y);
    showToast('Preferences saved.');
  } catch (error) {
    showToast(error.message || 'Preferences save failed.', 'error');
  }
}

async function saveSettingsSite() {
  if (!settingsIsStaff) { showToast('Company settings are staff-only.', 'error'); return; }
  const flag = (id) => (document.getElementById(id)?.checked ? 'true' : 'false');
  const entries = {
    overtime_min_hours: document.getElementById('setOtMin')?.value,
    overtime_max_hours: document.getElementById('setOtMax')?.value,
    purge_retention_days: document.getElementById('setPurgeDays')?.value,
    onboarding_max_mb: document.getElementById('setUploadCap')?.value,
    leave_restrict_backdated: flag('setLeaveBackdated'),
    leave_auto_allocate_days: document.getElementById('setLeaveAutoDays')?.value,
    shift_allow_double_booking: flag('setShiftDouble'),
    mobile_checkin_enabled: flag('setMobileCheckin'),
  };
  openSettingsConfirm('Save company settings?', 'Leave, shift, payroll, mobile and system rules update for everyone.', async () => {
    try {
      const res = await apiFetch('/api/settings/site/', { method: 'PATCH', body: JSON.stringify(entries) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.error === 'string' ? data.error : 'save failed');
      renderSettingsSite(data);
      showToast('Company settings saved.');
    } catch (error) {
      showToast(error.message || 'Company save failed.', 'error');
    }
  });
}

function renderSettingsImportPreview(rows) {
  const body = document.getElementById('settingsImportResults');
  if (!body) return;
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="4">No roster rows found.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((row) => {
    const name = [row.first_name, row.last_name].filter(Boolean).join(' ') || '—';
    const status = row.errors?.length ? row.errors.join(' ') : row.status || (row.ok ? 'Ready' : 'Needs attention');
    return `<tr><td>${escapeHtml(String(row.row ?? '—'))}</td><td>${escapeHtml(name)}</td><td>${escapeHtml(String(row.email || '—'))}</td><td title="${escapeHtml(`Row ${row.row ?? '—'}: ${status}`)}">${escapeHtml(String(status))}</td></tr>`;
  }).join('');
}

function settingsImportFormData() {
  const file = document.getElementById('settingsImportFile')?.files?.[0];
  if (!file) { showToast('Choose an .xlsx roster first.', 'error'); return null; }
  const form = new FormData();
  form.append('file', file);
  return { form, file };
}

async function settingsImportDryRun() {
  const upload = settingsImportFormData();
  if (!upload) return;
  try {
    const res = await apiFetch('/api/settings/import-employees/?dry_run=true', { method: 'POST', body: upload.form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Roster preview failed.');
    settingsCache = { ...(settingsCache || {}), _importPreview: data.rows || [], _importPreviewFile: upload.file };
    renderSettingsImportPreview(data.rows || []);
    const ready = (data.rows || []).filter((row) => row.ok).length;
    showToast(`Preview ready: ${ready} of ${(data.rows || []).length} row(s) can be imported.`);
  } catch (error) { showToast(error.message || 'Roster preview failed.', 'error'); }
}

async function settingsImportCommit() {
  const preview = (settingsCache && settingsCache._importPreview) || [];
  const ready = preview.filter((row) => row.ok);
  if (!ready.length) { showToast('Run a preview with at least one valid row first.', 'error'); return; }
  const upload = settingsImportFormData();
  if (!upload) return;
  if (settingsCache?._importPreviewFile !== upload.file) {
    showToast('The selected file changed. Run a new preview before importing.', 'error');
    return;
  }
  openSettingsConfirm('Import roster?', `${ready.length} valid employee row(s) will be created.`, async () => {
    try {
      const res = await apiFetch('/api/settings/import-employees/', { method: 'POST', body: upload.form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Roster import failed.');
      const failedByRow = new Map((data.failed || []).map((failure) => [failure.row, failure.error]));
      const results = preview.map((row) => ({
        ...row,
        status: failedByRow.has(row.row) ? failedByRow.get(row.row) : row.ok ? 'Imported' : 'Not imported',
        errors: [],
        ok: false,
      }));
      settingsCache._importPreview = results;
      renderSettingsImportPreview(results);
      showToast(`Import complete: ${data.created || 0} created, ${(data.failed || []).length} failed.`);
    } catch (error) { showToast(error.message || 'Roster import failed.', 'error'); }
  });
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
      if (data.requires_2fa) {
        try {
          if (document.getElementById('rememberMeCheckbox')?.checked) localStorage.setItem('kumon.employeeLogin', username);
          else localStorage.removeItem('kumon.employeeLogin');
        } catch (_) { /* storage can be disabled */ }
        const form = document.getElementById('employeeLoginForm');
        const challenge = document.getElementById('employeeMfaChallenge');
        if (form) form.hidden = true;
        if (challenge) challenge.hidden = false;
        document.getElementById('employeeMfaCode')?.focus();
        return { challenge: true };
      }
      return data;
    })
    .then((data) => {
      if (!data) return;
      if (data.challenge) return;
      const remember = document.getElementById('rememberMeCheckbox')?.checked;
      try {
        if (remember) localStorage.setItem('kumon.employeeLogin', username);
        else localStorage.removeItem('kumon.employeeLogin');
      } catch (_) { /* storage can be disabled */ }
      window.kumonLoadingNavigate(data.next_url, '/employee/');
    })
    .catch(() => showToast('Sign-in service unreachable. Try again later.', 'error'));
}

function initRememberedLogin() {
  const input = document.getElementById('loginEmployeeId');
  const checkbox = document.getElementById('rememberMeCheckbox');
  if (!input) return;
  try {
    const saved = localStorage.getItem('kumon.employeeLogin');
    if (saved) input.value = saved;
    if (checkbox) checkbox.checked = !!saved;
  } catch (_) { /* storage can be disabled */ }
}

async function handleEmployeeTwoFactor(event) {
  event.preventDefault();
  const csrf = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1];
  try {
    const response = await fetch('/api/session-verify-2fa/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
      body: JSON.stringify({ code: document.getElementById('employeeMfaCode')?.value.trim() || '' }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'That code could not be verified.');
    window.kumonLoadingNavigate(data.next_url, '/employee/');
  } catch (error) { showToast(error.message || 'Verification failed.', 'error'); }
}

async function cancelEmployeeTwoFactor() {
  const csrf = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1];
  await fetch('/api/session-cancel-2fa/', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
    body: '{}',
  });
  const code = document.getElementById('employeeMfaCode'); if (code) code.value = '';
  const challenge = document.getElementById('employeeMfaChallenge'); if (challenge) challenge.hidden = true;
  const form = document.getElementById('employeeLoginForm'); if (form) form.hidden = false;
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
    showToast('If an account can be created, check your email for a confirmation link.', 'success');
  } catch (err) {
    showToast('Sign-up service unreachable. Try again later.', 'error');
  }
}

function navigateToLogin(mode = 'login') {
  const currentPath = window.location.pathname.toLowerCase();
  const isFileProtocol = window.location.protocol === 'file:';

  if (mode === 'hr' && !isFileProtocol && !currentPath.endsWith('.html')) {
    window.location.href = '/hr/login/';
    return;
  }

  if (isFileProtocol || currentPath.endsWith('.html')) {
    window.location.href = `login.html#${mode}`;
  } else {
    window.location.href = `/login/#${mode}`;
  }
}

function signOut() {
  showToast('Signing out of corporate session...');
  apiFetch('/api/session-logout/', { method: 'POST' })
    .catch(() => { })
    .finally(() => navigateToLogin(window.location.pathname.startsWith('/hr') ? 'hr' : 'login'));
}

// ==========================================================================
// Audit Logs View Handlers
// ==========================================================================
let activeLogTabCategory = 'all';

function classifyAuditAction(actionText = '') {
  const text = String(actionText || '').toLowerCase();
  if (!text) return 'Personnel';
  if (/(leave|vacation|sick|pto|absence|holiday)/.test(text)) return 'Leaves';
  if (/(claim|expense|payroll|salary|deduction|advance|bonus|reimbursement)/.test(text)) return 'Claims';
  if (/(shift|roster|schedule|coverage|rotation|swap)/.test(text)) return 'Shifts';
  if (/(griev|complaint|mediation|investigation|case|resolution)/.test(text)) return 'Grievance';
  return 'Personnel';
}

function filterLogsByTab(category, btnElement) {
  activeLogTabCategory = category;
  const tabs = document.querySelectorAll('#view-logs .pill-tabs-container .tab-pill, #view-logs .claims-subtabs-bar .claims-subtab');
  tabs.forEach(tab => tab.classList.remove('active'));
  if (btnElement) {
    btnElement.classList.add('active');
  }

  filterAuditLogs();
}

function filterAuditLogs() {
  const searchInput = document.getElementById('auditSearchInput');
  const adminSelect = document.getElementById('auditAdminFilter');

  const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
  const selectedCategory = activeLogTabCategory === 'all' ? '' : activeLogTabCategory;
  const selectedAdmin = adminSelect ? adminSelect.value : '';

  const rows = document.querySelectorAll('#auditLogsTableBody tr[data-live="true"]');
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
    const liveTotal = Number.isFinite(auditLiveTotal) ? auditLiveTotal : visibleCount;
    paginationInfo.textContent = `${visibleCount} events on this page · ${liveTotal.toLocaleString()} total`;
  }
}

// Attendance register export: use live table rows or fetch backend data.
async function exportAttendanceRegister() {
  const body = document.getElementById('attendanceTableBody');
  const live = body ? Array.from(body.querySelectorAll('tr[data-live="true"]')) : [];
  const rows = [['Date', 'Employee', 'Role', 'Assigned Shift', 'Clock In', 'Clock Out', 'Status']];

  if (live.length) {
    const visible = live.filter((tr) => tr.style.display !== 'none');
    const targets = visible.length ? visible : live;
    targets.forEach((tr) => {
      const date = tr.dataset.attendanceDate || (typeof attendanceSelectedDate !== 'undefined' ? attendanceSelectedDate : '') || '';
      const nameEl = tr.querySelector('.bold-title');
      const roleEl = tr.querySelector('.sub-role');
      const tds = tr.querySelectorAll('td');
      const empName = nameEl ? nameEl.textContent.trim() : (tds[0] ? tds[0].textContent.trim() : '');
      const empRole = roleEl ? roleEl.textContent.trim() : '';
      const shift = tds[1] ? tds[1].textContent.trim() : '';
      const clockIn = tds[2] ? tds[2].textContent.trim() : '';
      const clockOut = tds[3] ? tds[3].textContent.trim() : '';
      const status = tds[4] ? tds[4].textContent.trim().replace(/^[●\s]+/, '') : '';
      rows.push([date, empName, empRole, shift, clockIn, clockOut, status]);
    });
  } else {
    try {
      const [records, employees] = await Promise.all([
        fetchAllApiRows('/api/attendance/?page_size=100'),
        fetchAllApiRows('/api/employees/?page_size=100').catch(() => []),
      ]);
      const empById = Object.fromEntries(employees.map((employee) => [employee.id, employee]));
      records.forEach((a) => {
        const emp = empById[a.employee] || {};
        const empName = a.employee_name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim() || emp.email || a.employee || 'Employee';
        const empRole = a.employee_role || emp.role || 'Staff';
        const shiftOrDept = a.employee_department || emp.department_name || 'Standard Shift';
        const status = a.clock_out ? 'Complete' : 'Clocked in';
        rows.push([
          a.date || '',
          empName,
          empRole,
          shiftOrDept,
          typeof fmtTime === 'function' ? fmtTime(a.clock_in) : (a.clock_in || ''),
          typeof fmtTime === 'function' ? fmtTime(a.clock_out) : (a.clock_out || ''),
          status,
        ]);
      });
    } catch (error) {
      showToast(error.message || 'Attendance records could not be loaded.', 'error');
      return;
    }
  }

  if (rows.length === 1) {
    showToast('No attendance records available to export.', 'error');
    return;
  }

  downloadCsv(`kumon_ems_attendance_${new Date().toISOString().slice(0, 10)}.csv`, rows);
  showToast(`Exported ${rows.length - 1} attendance record${rows.length === 2 ? '' : 's'}.`);
}

function downloadCsv(filename, rows) {
  if (!rows || !rows.length) return;
  const escapeCell = (val) => {
    const s = val == null ? '' : String(val);
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csvContent = '\uFEFF' + rows.map((r) => r.map(escapeCell).join(',')).join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportAuditLogs() {
  const rows = [['Timestamp', 'Administrator', 'Action Class', 'Action', 'Target Record', 'Details', 'Status', 'Audit ID']];
  let logs;
  let names = {};
  try {
    [logs, names] = await Promise.all([
      fetchAllApiRows('/api/audit-logs/?page_size=100'),
      liveEmployeeNames().catch(() => ({})),
    ]);
  } catch (error) {
    if (error.message !== 'auth') showToast(error.message || 'Audit logs could not be loaded.', 'error');
    return;
  }
  logs.forEach((log) => {
    const who = names[log.employee] || (log.employee ? `Employee #${log.employee}` : 'System');
    const when = log.timestamp ? new Date(log.timestamp).toLocaleString() : '';
    const category = classifyAuditAction(log.action || '');
    const actionText = formatAuditActionText(log.action || '');
    const target = log.target || log.target_record || (log.employee ? `EMP-${log.employee}` : '—');
    const details = log.details || log.notes || actionText;
    rows.push([
      when,
      who,
      category,
      actionText,
      target,
      details,
      'Logged',
      String(log.id || '').slice(0, 8),
    ]);
  });

  if (rows.length === 1) {
    showToast('No audit logs available to export.', 'error');
    return;
  }

  downloadCsv(`kumon_ems_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`, rows);
  showToast(`Exported ${rows.length - 1} audit log record${rows.length === 2 ? '' : 's'}.`);
}

// ==========================================================================
// Live API wiring: dashboard summary + employee directory
// ==========================================================================

// Minimal toast for pages without the shared dashboard shell.
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

// First-run empty state: point fresh installs at employee onboarding.
function renderFirstEmployeeCta(total) {
  const slot = document.getElementById('view-dashboard');
  if (!slot) return;
  let cta = document.getElementById('firstEmployeeCta');
  if (Number(total) !== 0) {
    if (cta) cta.remove();
    return;
  }
  if (cta) return;
  cta = document.createElement('div');
  cta.id = 'firstEmployeeCta';
  cta.className = 'white-card';
  cta.innerHTML =
    '<h2 class="card-title">No employees yet</h2>' +
    '<p class="card-sub">Add your first employee to unlock attendance, leave, and payroll.</p>' +
    '<div class="modal-foot" style="justify-content:flex-start;">' +
    '<button class="btn btn-navy-cta" onclick="switchView(\'employee-directory\')">Add your first employee</button></div>';
  slot.prepend(cta);
}

// Public aggregate counts for the landing page.
function loadDashboardSummary() {
  if (dashboardSummaryInFlight) return Promise.resolve();
  dashboardSummaryInFlight = true;
  return apiFetch('/api/dashboard-summary/', { headers: { Accept: 'application/json', 'Cache-Control': 'no-cache' }, cache: 'no-store' })
    .then((res) => {
      if (!res.ok) throw new Error('summary unavailable');
      return res.json();
    })
    .then((data) => {
      if (dashboardSummaryRetryTimer) {
        clearTimeout(dashboardSummaryRetryTimer);
        dashboardSummaryRetryTimer = null;
      }
      setApiMode('live');
      renderFirstEmployeeCta(data.total_employees);
      const values = document.querySelectorAll(
        '#view-dashboard .kpi-cards-4grid .kpi-card .kpi-value'
      );
      if (values.length >= 4) {
        values[0].textContent = data.total_employees;
        values[1].textContent = data.active_employees;
        values[2].textContent = String(data.approved_leaves || 0).padStart(2, '0');
        values[3].textContent = String(data.pending_leaves || 0).padStart(2, '0');
      }
      const attendanceCount = document.getElementById('dashboardAttendanceCount');
      const leaveCount = document.getElementById('dashboardLeaveCount');
      const claimsCount = document.getElementById('dashboardClaimsCount');
      if (attendanceCount) attendanceCount.textContent = (typeof data.attendance_month !== 'undefined' ? data.attendance_month : data.attendance_today) || 0;
      if (leaveCount) leaveCount.textContent = data.approved_leaves || 0;
      if (claimsCount) claimsCount.textContent = data.claims_count || 0;
    })
    .catch((err) => {
      if (err && err.message === 'auth') return; // apiFetch already redirected
      setApiMode('offline');
      if (dashboardSummaryFailures === 1 && !dashboardSummaryRetryTimer) {
        dashboardSummaryRetryTimer = window.setTimeout(() => {
          dashboardSummaryRetryTimer = null;
          const dashboardView = document.getElementById('view-dashboard');
          if (!document.hidden && dashboardView?.classList.contains('active')) loadDashboardSummary();
        }, 2500);
      }
    })
    .finally(() => { dashboardSummaryInFlight = false; });
}

async function loadDashboardAttendance() {
  const body = document.getElementById('dashboardAttendanceTableBody');
  if (!body) return;
  const today = localDateIso();
  try {
    const [attendanceRows, employees, departments] = await Promise.all([
      fetchAllApiRows('/api/attendance/?page_size=100'),
      fetchAllApiRows('/api/employees/?page_size=100'),
      fetchAllApiRows('/api/departments/?page_size=100'),
    ]);
    const attendance = attendanceRows.filter((record) => record.date === today);
    const employeeById = Object.fromEntries(employees.map((employee) => [employee.id, employee]));
    const departmentById = Object.fromEntries(departments.map((department) => [department.id, department.name]));
    body.innerHTML = '';
    if (!attendance.length) {
      body.innerHTML = '<tr><td colspan="5">No attendance records for today.</td></tr>';
      return;
    }
    attendance.forEach((record) => {
      const employee = employeeById[record.employee] || {};
      const name = `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || employee.email || record.employee;
      const status = record.clock_out ? 'Complete' : 'Clocked in';
      const row = document.createElement('tr');
      row.dataset.attendanceDate = record.date || '';
      row.innerHTML =
        `<td class="bold-title">${escapeHtml(name)}</td>` +
        `<td>${escapeHtml(departmentById[employee.department] || '—')}</td>` +
        `<td>${escapeHtml(employee.role || '—')}</td>` +
        `<td><span class="penpot-badge ${record.clock_out ? 'badge-pending' : 'badge-present'}">${status}</span></td>` +
        `<td>${escapeHtml(fmtTime(record.clock_in))}</td>`;
      body.appendChild(row);
    });
    filterAttendanceRegisterByDate();
  } catch (error) {
    body.innerHTML = '<tr><td colspan="5">Dashboard attendance is unavailable.</td></tr>';
  }
}

// Live employee directory keyed by lowercase full name (reused by the leave
// modal to resolve an applicant to an employee id). Auth-only endpoint:
// logged-out visitors are sent to the canonical login page.
const employeeNameIndex = {};

async function populateRosterEmployeeOptions() {
  const selects = ['morning', 'evening', 'night']
    .map((shiftKey) => document.getElementById(`staffSelect-${shiftKey}`))
    .filter(Boolean);
  if (!selects.length) return;
  try {
    const rows = (await fetchAllApiRows('/api/employees/?page_size=100'))
      .filter((employee) => employee.is_active !== false);
    selects.forEach((select) => {
      select.innerHTML = '<option value="">Select Employee...</option>';
      rows.forEach((employee) => {
        const name = `${employee.first_name || ''} ${employee.last_name || ''}`.trim();
        const option = document.createElement('option');
        option.value = employee.id;
        option.dataset.name = name || employee.email || employee.id;
        option.dataset.role = employee.role || 'Employee';
        option.dataset.initials = (name || employee.email || 'E')
          .split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
        option.textContent = name || employee.email || employee.id;
        select.appendChild(option);
      });
      if (!rows.length) select.innerHTML = '<option value="">No active employees found</option>';
    });
  } catch (_) {
    selects.forEach((select) => {
      select.innerHTML = '<option value="">Unable to load employees</option>';
    });
    showToast('Employee roster could not be loaded.', 'error');
  }
}

async function loadEmployeeOptions(selectId) {
  const select = document.getElementById(selectId);
  if (!select) return;
  try {
    const rows = await fetchAllApiRows('/api/employees/?page_size=100');
    select.replaceChildren(new Option('Select an active employee...', ''));
    select.options[0].disabled = true;
    select.options[0].selected = true;
    rows.filter((employee) => employee.is_active !== false).forEach((employee) => {
      const fullName = `${employee.first_name || ''} ${employee.last_name || ''}`.trim();
      const option = document.createElement('option');
      option.value = employee.id;
      option.textContent = fullName || employee.email || employee.id;
      select.appendChild(option);
      if (fullName) employeeNameIndex[fullName.toLowerCase()] = employee.id;
      if (employee.email) employeeNameIndex[employee.email.toLowerCase()] = employee.id;
    });
    if (select.options.length === 1) select.options[0].textContent = 'No active employees found';
  } catch (_) {
    select.replaceChildren(new Option('Unable to load employees', ''));
    select.options[0].disabled = true;
    showToast('Employee directory could not be loaded.', 'error');
  }
}

function loadEmployeeDirectory() {
  const list = document.getElementById('employeeRosterList');
  if (!list) return;
  list.innerHTML = '<div class="directory-empty-state">Loading employees from the database...</div>';
  Promise.all([
    fetchAllApiRows('/api/employees/?page_size=100'),
    fetchAllApiRows('/api/departments/?page_size=100'),
  ])
    .then(([rows, departments]) => {
      const departmentNames = Object.fromEntries(departments.map((department) => [department.id, department.name || '']));
      const departmentFilter = document.getElementById('deptFilter');
      const roleFilter = document.getElementById('roleFilter');
      const statusFilter = document.getElementById('statusFilter');
      const setFilterOptions = (select, label, values) => {
        if (!select) return;
        const selected = select.value;
        select.replaceChildren(new Option(label, 'all'));
        [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b)).forEach((value) => {
          const option = new Option(value, value);
          select.appendChild(option);
        });
        select.value = [...select.options].some((option) => option.value === selected) ? selected : 'all';
      };
      const getStatus = (employee) => employee.resigned_at
        ? 'Resigned'
        : employee.is_active === false ? 'Inactive' : 'Active';
      setFilterOptions(departmentFilter, 'All Departments', [
        ...departments.map((department) => department.name),
        ...(rows.some((employee) => !employee.department) ? ['Unassigned'] : []),
      ]);
      setFilterOptions(roleFilter, 'All Roles', [
        ...rows.map((employee) => employee.role || ''),
        ...(rows.some((employee) => !employee.role) ? ['Unassigned'] : []),
      ]);
      setFilterOptions(statusFilter, 'All Statuses', rows.map(getStatus));
      list.innerHTML = '';
      rows.forEach((emp) => {
        const fullName = `${emp.first_name || ''} ${emp.last_name || ''}`.trim() || emp.email || 'Employee';
        const department = emp.department_name || departmentNames[emp.department] || 'Unassigned';
        const role = emp.role || 'Unassigned';
        const status = getStatus(emp);
        employeeNameIndex[fullName.toLowerCase()] = emp.id;
        const card = document.createElement('div');
        card.className = 'roster-accordion-card';
        card.setAttribute('data-live', 'true');
        card.setAttribute('data-emp-id', emp.id);
        card.setAttribute('data-dept', department);
        card.setAttribute('data-role', role);
        card.setAttribute('data-status', status);
        const badgeClass = status === 'Active' ? 'badge-present' : 'badge-pending';
        card.innerHTML =
          `<div class="acc-summary" onclick="toggleAccordion(this)">` +
          `<div class="acc-left">` +
          `<strong class="acc-name">${escapeHtml(fullName)}</strong>` +
          `<span class="acc-role">${escapeHtml(role)} &bull; ${escapeHtml(department)}</span>` +
          `</div>` +
          `<div class="acc-right">` +
          `<span class="penpot-badge ${badgeClass}">` +
          `${escapeHtml(status)}</span>` +
          `</div></div>` +
          `<div class="acc-expanded-body" hidden>` +
          `<div class="acc-col"><span class="col-head">CONTACT</span>` +
          `<div class="perf-text">${escapeHtml(emp.email || '')}</div>` +
          `<div class="acc-btn-row">` +
          `<button class="btn btn-black-sm" onclick="focusRosterProfile(this)">Open profile details</button>` +
          `<button class="btn btn-purple-outline-sm" data-name="${escapeHtml(fullName)}" onclick="messageInApp(this.dataset.name)">Message in app</button>` +
          `</div></div></div>`;
        list.appendChild(card);
      });
      if (!rows.length) list.innerHTML = '<div class="directory-empty-state">No employees found in the database.</div>';
      if (typeof filterDirectory === 'function') filterDirectory();
    })
    .catch((err) => {
      if (err && err.message === 'auth') return; // apiFetch already redirected
      list.innerHTML = '<div class="directory-empty-state">Employee data is unavailable.</div>';
      showToast('Employee data could not be loaded.', 'error');
    });
}

// ==========================================================================
// Live view wiring: render backend data and show an explicit unavailable state.
// ==========================================================================
let liveEmployeeNameCache = null;
async function liveEmployeeNames() {
  if (liveEmployeeNameCache) return liveEmployeeNameCache;
  const rows = await fetchAllApiRows('/api/employees/?page_size=100');
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
  body.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">Loading attendance…</td></tr>';
  try {
    const todayLocal = localDateIso();
    const [rows, employees, shifts, leavesAll] = await Promise.all([
      fetchAllApiRows('/api/attendance/?page_size=100'),
      fetchAllApiRows('/api/employees/?page_size=100&is_active=true').catch(() => []),
      fetchAllApiRows(`/api/shift-rosters/?page_size=100&work_date=${todayLocal}`).catch(() => []),
      fetchAllApiRows('/api/leaves/?page_size=100').catch(() => []),
    ]);
    const empById = Object.fromEntries(employees.map((employee) => [employee.id, employee]));
    const empCount = employees.length;
    const leavesToday = leavesAll.filter(l => l.status === 'Approved' && l.start_date <= todayLocal && l.end_date >= todayLocal);

    const attToday = rows.filter(r => r.date === todayLocal);
    const presentToday = attToday.filter(r => r.clock_in).length;
    const scheduled = shifts.length > 0 ? shifts.length : empCount;
    const onLeaveCount = leavesToday.length;
    const exceptions = Math.max(0, scheduled - presentToday - onLeaveCount);

    const prEl = document.getElementById('att-kpi-present');
    if (prEl) {
      prEl.textContent = String(presentToday).padStart(2, '0');
      document.getElementById('att-kpi-present-sub').textContent = `${presentToday} / ${scheduled} Scheduled Staff`;
      document.getElementById('att-kpi-scheduled').textContent = String(scheduled).padStart(2, '0');
      document.getElementById('att-kpi-scheduled-sub').textContent = scheduled > 0 ? `${Math.round((presentToday / scheduled) * 100)}% Roster Filled` : '0% Roster Filled';
      document.getElementById('att-kpi-exceptions').textContent = String(exceptions).padStart(2, '0');
      document.getElementById('att-kpi-exceptions-sub').textContent = `${exceptions} Unexcused Absence${exceptions !== 1 ? 's' : ''}`;
      document.getElementById('att-kpi-onleave').textContent = String(onLeaveCount).padStart(2, '0');
      document.getElementById('att-kpi-onleave-sub').textContent = `${onLeaveCount} Staff on Leave`;
    }

    attendanceLoggedDates = new Set(rows.map((r) => r.date).filter(Boolean));
    renderAttendanceCalendar();

    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr class="attendance-empty-row"><td colspan="5" style="text-align:center; padding: 28px; color: #64748b;">No attendance records found. Click Clock in above to record attendance.</td></tr>';
    } else {
      rows.forEach((a) => {
        const open = !a.clock_out;
        const emp = empById[a.employee] || {};
        const empName = a.employee_name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim() || emp.email || a.employee || 'Employee';
        const empRole = a.employee_role || emp.role || 'Staff';
        const shiftOrDept = a.employee_department || emp.department_name || 'Standard Shift';
        const tr = document.createElement('tr');
        tr.setAttribute('data-live', 'true');
        tr.dataset.attendanceDate = a.date || '';
        tr.innerHTML =
          `<td><div class="bold-title">${escapeHtml(String(empName))}</div>` +
          `<div class="sub-role">${escapeHtml(String(empRole))}</div></td>` +
          `<td>${escapeHtml(String(shiftOrDept))}</td><td>${escapeHtml(fmtTime(a.clock_in))}</td><td>${escapeHtml(fmtTime(a.clock_out))}</td>` +
          `<td><span class="penpot-badge ${open ? 'badge-present' : 'badge-pending'}">` +
          `${open ? '● Clocked in' : 'Complete'}</span></td>`;
        body.appendChild(tr);
      });
    }
    filterAttendanceRegisterByDate();
  } catch (e) {
    body.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: #ef4444;">Attendance data is unavailable.</td></tr>';
    showToast('Attendance data could not be loaded.', 'error');
  }
}

async function submitSelfAttendance(action) {
  const buttonId = action === 'clock_in' ? 'portalClockInButton' : 'portalClockOutButton';
  const button = document.getElementById(buttonId);
  if (button) button.disabled = true;
  try {
    const res = await apiFetch('/api/attendance/me/', {
      method: 'POST',
      body: JSON.stringify({ action }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Attendance could not be recorded.');
    showToast(action === 'clock_in' ? 'Clock-in recorded.' : 'Clock-out recorded.');
    await loadAttendanceView();
    loadDashboardSummary();
    loadDashboardAttendance();
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    if (button) button.disabled = false;
  }
}

async function submitAttendanceCheckIn(event) {
  event.preventDefault();
  const nameInput = document.getElementById('attendanceEmployeeName');
  const passwordInput = document.getElementById('attendancePassword');
  const button = document.getElementById('attendanceCheckInButton');
  const status = document.getElementById('attendanceCheckInStatus');
  const csrf = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=')[1];
  if (!nameInput || !passwordInput || !button || !status) return;

  button.disabled = true;
  status.textContent = 'Checking your details...';
  try {
    const response = await fetch('/api/attendance/check-in/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}) },
      body: JSON.stringify({ name: nameInput.value.trim(), password: passwordInput.value }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Unable to record attendance.');
    status.textContent = data.already_present
      ? `${data.employee} is already marked present today.`
      : `${data.employee} is now marked present.`;
    status.style.color = '#166534';
    passwordInput.value = '';
    loadDashboardSummary();
    loadDashboardAttendance();
    loadAttendanceView();
  } catch (error) {
    status.textContent = error.message;
    status.style.color = '#b91c1c';
  } finally {
    button.disabled = false;
  }
}

async function loadShiftRosterView() {
  const body = document.getElementById('shiftRosterTableBody');
  if (!body) return;
  try {
    const rows = await fetchAllApiRows('/api/shift-rosters/?page_size=100');
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
    refreshShiftConflictBadges();
  } catch (e) {
    body.innerHTML = '<tr><td colspan="5">Shift roster is unavailable. Try refreshing.</td></tr>';
    showToast('Shift roster could not be loaded.', 'error');
  }
}

async function loadMasterShiftCalendar(selectedDate) {
  const head = document.getElementById('shiftMatrixHead');
  const body = document.getElementById('shiftMatrixBody');
  if (!head || !body) return;
  const pickerDate = selectedDate || document.getElementById('shiftDatePicker')?.value;
  const anchor = pickerDate ? new Date(`${pickerDate}T00:00:00`) : new Date();
  if (Number.isNaN(anchor.getTime())) return;
  const monday = new Date(anchor);
  const day = monday.getDay();
  monday.setDate(monday.getDate() - (day === 0 ? 6 : day - 1));
  const dates = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + index);
    return date;
  });
  const iso = (date) => [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
  const selectedIso = iso(anchor);
  try {
    const [employeeRows, rosters] = await Promise.all([
      fetchAllApiRows('/api/employees/?page_size=100'),
      fetchAllApiRows('/api/shift-rosters/?page_size=100'),
    ]);
    const employees = employeeRows.filter((employee) => employee.is_active !== false);
    const byEmployeeDate = {};
    rosters.forEach((roster) => {
      if (roster.work_date) {
        const key = `${roster.employee}:${roster.work_date}`;
        (byEmployeeDate[key] ||= []).push(roster);
      }
    });
    head.innerHTML = `<tr><th class="col-staff">EMPLOYEE</th>${dates.map((date) => {
      const isSelected = iso(date) === selectedIso;
      return `<th class="${isSelected ? 'col-today' : ''}">${date.toLocaleDateString([], { weekday: 'short' }).toUpperCase()}<br><strong>${date.toLocaleDateString([], { day: 'numeric', month: 'short' })}${isSelected ? ' • Selected' : ''}</strong></th>`;
    }).join('')}</tr>`;
    body.innerHTML = '';
    if (!employees.length) {
      body.innerHTML = '<tr><td colspan="8">No active employees found.</td></tr>';
    } else {
      employees.forEach((employee) => {
        const name = `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || employee.email || 'Employee';
        const initials = name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
        const cells = dates.map((date) => {
          const dayRosters = byEmployeeDate[`${employee.id}:${iso(date)}`] || [];
          if (!dayRosters.length) return '<td><div class="shift-capsule shift-off"><span class="shift-code">OFF</span><span class="shift-status">Unassigned</span></div></td>';
          return `<td>${dayRosters.map((roster) => `<div class="shift-capsule ${iso(date) === selectedIso ? 'shift-flex' : ''}"><span class="shift-code">${escapeHtml(String(roster.shift_type || 'SHIFT').toUpperCase())}</span><span class="shift-status">${escapeHtml(String(roster.start_time || '').slice(0, 5))} – ${escapeHtml(String(roster.end_time || '').slice(0, 5))}</span></div>`).join('')}</td>`;
        }).join('');
        body.insertAdjacentHTML('beforeend', `<tr><td><div class="shift-staff-cell"><div class="shift-staff-avatar">${escapeHtml(initials)}</div><div class="shift-staff-meta"><strong>${escapeHtml(name)}</strong><span>${escapeHtml(employee.role || 'Employee')}</span></div></div></td>${cells}</tr>`);
      });
    }
    const weekLabel = document.getElementById('shiftWeekLabel');
    if (weekLabel) weekLabel.textContent = `${dates[0].toLocaleDateString([], { month: 'short', day: 'numeric' })} – ${dates[6].toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
  } catch (_) {
    body.innerHTML = '<tr><td colspan="8">Roster calendar data is unavailable.</td></tr>';
  }
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
    const [runs, items] = await Promise.all([
      fetchAllApiRows('/api/payroll-runs/?page_size=100'),
      fetchAllApiRows('/api/payroll-items/?page_size=100'),
    ]);
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
  } catch (e) {
    body.innerHTML = '<tr><td colspan="4">Payroll data is unavailable. Try refreshing.</td></tr>';
    showToast('Payroll data could not be loaded.', 'error');
  }
}

async function loadAuditView() {
  auditPagerPage = 1;
  return auditPagerGoto(1);
}

// Audit pager (D34): ?page=N against /api/audit-logs/.
let auditPagerPage = 1;
const AUDIT_PAGE_SIZE = 10;
// Live total from the last audit fetch.
let auditLiveTotal = 0;

function auditPagerStep(delta) {
  auditPagerGoto(auditPagerPage + delta);
}

function buildAuditRow(log, names) {
  const who = names[log.employee] || 'System';
  const category = classifyAuditAction(log.action);
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
  try {
    const res = await apiFetch(`/api/audit-logs/?page=${page}&page_size=${AUDIT_PAGE_SIZE}`);
    if (!res.ok) throw new Error('load failed');
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : payload.results || [];
    const total = typeof payload.count === 'number' ? payload.count : rows.length;
    const totalPages = Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE));
    if (page > totalPages) return auditPagerGoto(totalPages);
    let names = {};
    try { names = await liveEmployeeNames(); } catch (_) { /* fall back to System */ }
    body.innerHTML = '';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7">No audit events on this page yet.</td></tr>';
    } else {
      rows.forEach((log) => body.appendChild(buildAuditRow(log, names)));
    }
    auditPagerPage = page;
    auditLiveTotal = total;
    updatePagerControls('audit', page, total, AUDIT_PAGE_SIZE);
    markPagerActive('audit', page);
    filterAuditLogs();
  } catch (e) {
    body.innerHTML = '<tr><td colspan="7">This audit page is unavailable. Try refreshing.</td></tr>';
    showToast('Audit page could not be loaded.', 'error');
  }
}

