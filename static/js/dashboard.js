/* ==========================================================================
   Kumon EMS - Interactive Logic & State Management
   ========================================================================== */


document.addEventListener('DOMContentLoaded', () => {
  initBrandLogo();
  initNavigation();
  loadDashboardSummary();
  loadEmployeeDirectory();
  loadClaimStatuses();
  loadMessagesForConversation('sarah');
  loadAttendanceView();
  loadShiftRosterView();
  loadAuditView();
});

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
  if (e.key === "Escape") { hideShortcutHelp(); kumonKeyPrefix = null; return; }
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

// Accordion toggle for Employee Directory
function toggleAccordion(summaryElement) {
  const card = summaryElement.closest('.roster-accordion-card');
  const tag = summaryElement.querySelector('.acc-toggle-tag');
  
  if (card.classList.contains('open')) {
    card.classList.remove('open');
    if (tag) {
      tag.innerHTML = `<svg class="chevron-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg> <span>Expand Profile</span>`;
    }
  } else {
    card.classList.add('open');
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

  const cards = document.querySelectorAll('#employeeRosterList .roster-accordion-card');
  cards.forEach(card => {
    const cardDept = (card.getAttribute('data-dept') || '').toLowerCase();
    const cardRole = (card.getAttribute('data-role') || '').toLowerCase();
    const cardStatus = (card.getAttribute('data-status') || '').toLowerCase();

    const matchesDept = (dept === 'all' || cardDept === dept);
    const matchesRole = (role === 'all' || cardRole === role);
    const matchesStatus = (status === 'all' || cardStatus === status);

    if (matchesDept && matchesRole && matchesStatus) {
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

// Offboarding handler — resolves the employee by corporate email, then
// DELETEs via the existing soft-delete (resign) flow.
async function handleOffboardingSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const email = form.querySelector('input[type="email"]')?.value.trim() || '';
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
    showToast('Offboarding finalized and exit clearance issued successfully!');
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

// Onboarding form submit handler: POST the wizard fields to the live API.
function handleOnboarding(e) {
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
      showToast(`Employee ${fullName || email} created & credentials issued!`);
      closeOnboardingModal();
      form.reset();
      loadEmployeeDirectory();
    })
    .catch(() => showToast('Unable to create employee upstream. Try again later.', 'error'));
}

// Grievance handler
function handleGrievanceSubmit(e) {
  e.preventDefault();
  showToast('Confidential grievance filed and assigned to HR Mediator.');
  e.target.reset();
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
  showToast(`Assigned ${name} (${roleTag}) successfully!`);
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
function showToast(message) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
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
  const response = await apiFetch('/api/claim-statuses/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claim_id: id, status })
  });
  if (!response.ok) throw new Error('Unable to save claim status.');
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
}

async function batchApproveClaims() {
  const pendingBadges = document.querySelectorAll('#pendingClaimsTableBody .claims-status-pill.pending');
  for (const b of pendingBadges) {
    const id = b.id.replace('status-', '');
    try {
      await saveClaimStatus(id, 'Approved');
      renderClaimStatus(id, 'Approved');
    } catch (error) {
      showToast('Claim status could not be saved.');
      return;
    }
  }
  showToast('Batch approved all active pending expense claims.');
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

function handleRequestAdvance(e) {
  e.preventDefault();
  closeAdvanceModal();
  showToast('Salary advance application submitted for HR cap verification.');
  e.target.reset();
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
  if (file) showToast(`${file.name} attached. Add a message or press Send Message.`);
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
    paginationInfo.textContent = `Showing ${visibleCount} of 1,482 logged admin events`;
  }
}

function exportAuditLogs() {
  showToast('Exporting admin audit log trail (CSV)...');
  const csvRows = [
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
  ];

  const csvContent = 'data:text/csv;charset=utf-8,' + csvRows.map(e => e.map(i => `"${i}"`).join(',')).join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `kumon_ems_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
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
    .then((data) => {
      setApiMode('live');
      const rows = Array.isArray(data) ? data : data.results || [];
      list.innerHTML = '';
      rows.forEach((emp) => {
        const fullName = `${emp.first_name || ''} ${emp.last_name || ''}`.trim();
        employeeNameIndex[fullName.toLowerCase()] = emp.id;
        const card = document.createElement('div');
        card.className = 'roster-accordion-card';
        card.setAttribute('data-live', 'true');
        card.setAttribute('data-dept', emp.department_name || '');
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
          `${emp.is_active === false ? 'Inactive' : 'Active'}</span>` +
          `</div></div>`;
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


