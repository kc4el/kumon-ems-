/* ==========================================================================
   peopleops (Kumon EMS) - Interactive Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initSearch();
});

// View Navigation Mapping
const viewBreadcrumbs = {
  'dashboard': { active: 'Overview' },
  'employee-directory': { active: 'Employee Directory' },
  'employee-manage': { root: 'Employees', active: 'Manage Staff' },
  'employee-grievance': { root: 'Employees', active: 'Grievance Tracker' },
  'attendance-daily': { root: 'Attendance', active: 'Daily Attendance & Time Log' },
  'attendance-shift': { root: 'Attendance', active: 'Shift Scheduling & Roster' },
  'attendance-leave': { root: 'Attendance', active: 'Leave & Absence Management' },
  'payroll': { root: 'Payroll', active: 'Payroll Ledger' },
  'profile': { active: 'Profile' },
  'my-details': { active: 'Profile' },
  'claims': { active: 'Claims & Reimbursements' },
  'reports': { active: 'Reports & Analytics' }
};

function initNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
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
       ((viewName === 'profile' || viewName === 'my-details') && dataView === 'profile')) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Hide all view panels
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.remove('active');
  });

  // Show target view panel or placeholder
  const targetPanel = document.getElementById(`view-${viewName}`);
  if (targetPanel) {
    targetPanel.classList.add('active');
  } else {
    // Show placeholder view with specific title
    const placeholderPanel = document.getElementById('view-placeholder');
    const placeholderTitle = document.getElementById('placeholderTitle');
    if (placeholderPanel && placeholderTitle) {
      placeholderTitle.textContent = viewName.replace('-', ' ').toUpperCase();
      placeholderPanel.classList.add('active');
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

// Accordion toggle for Employee Directory
function toggleAccordion(summaryElement) {
  const card = summaryElement.closest('.roster-accordion-card');
  const tag = summaryElement.querySelector('.acc-toggle-tag');
  
  if (card.classList.contains('open')) {
    card.classList.remove('open');
    if (tag) tag.textContent = '▼ Expand Profile';
  } else {
    card.classList.add('open');
    if (tag) tag.textContent = '▲ Collapse Profile';
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

// Promote vs Transfer mode switch
function setPtMode(mode) {
  const btnPromote = document.getElementById('btnModePromote');
  const btnTransfer = document.getElementById('btnModeTransfer');
  const title = document.getElementById('ptCardTitle');
  const subtitle = document.getElementById('ptCardSubtitle');
  const promoteContainer = document.getElementById('promoteFormContainer');
  const transferContainer = document.getElementById('transferFormContainer');

  if (mode === 'promote') {
    btnPromote.classList.add('active');
    btnTransfer.classList.remove('active');
    title.textContent = 'Promote Employee';
    subtitle.textContent = 'Record the next role and pay-grade step with a clear effective date and promotion rationale.';
    promoteContainer.style.display = 'block';
    transferContainer.style.display = 'none';
  } else {
    btnTransfer.classList.add('active');
    btnPromote.classList.remove('active');
    title.textContent = 'Transfer employee';
    subtitle.textContent = 'Move a person to a new team or work location and keep the effective date and rationale on the record.';
    promoteContainer.style.display = 'none';
    transferContainer.style.display = 'block';
  }
}

// Onboarding handler
function handleOnboarding(e) {
  e.preventDefault();
  showToast('New employee profile created & credentials issued successfully!');
  e.target.reset();
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
    if (txt) txt.textContent = '⌃ Collapse Calendar';
    showToast('Shift Roster Master Calendar expanded.');
  } else {
    cal.classList.add('collapsed');
    if (txt) txt.textContent = '⌄ Expand Calendar';
    showToast('Shift Roster Master Calendar collapsed.');
  }
}

function focusQuickAssign(shiftName) {
  const select = document.getElementById('qaShiftSelect');
  if (select) {
    select.value = shiftName;
    select.scrollIntoView({ behavior: 'smooth', block: 'center' });
    select.focus();
  }
}

function removeShiftStaff(btn) {
  const userRow = btn.closest('.shift-slot-user-row');
  if (userRow) {
    userRow.style.opacity = '0';
    userRow.style.transform = 'scale(0.95)';
    userRow.style.transition = 'all 0.2s ease';
    setTimeout(() => {
      userRow.remove();
      showToast('Employee removed from shift slot.');
    }, 200);
  }
}

function handleQuickAssignShift(e) {
  e.preventDefault();
  const shift = document.getElementById('qaShiftSelect').value;
  const employee = document.getElementById('qaEmployeeSelect').value;
  const role = document.getElementById('qaRoleSelect').value;

  showToast(`Assigned ${employee} (${role}) to ${shift} successfully!`);
  e.target.reset();
}

// ==========================================================================
// Claims & Reimbursements Handlers
// ==========================================================================
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

function handleClaimAction(id, action) {
  const statusElem = document.getElementById(`status-${id}`);
  const actionsElem = document.getElementById(`actions-${id}`);

  if (action === 'Approve') {
    if (statusElem) {
      statusElem.className = 'claims-status-pill approved';
      statusElem.textContent = '● Approved';
    }
    showToast(`Claim ${id} approved for reimbursement settlement.`);
  } else {
    if (statusElem) {
      statusElem.className = 'claims-status-pill rejected';
      statusElem.textContent = '● Rejected';
    }
    showToast(`Claim ${id} flagged and marked as rejected.`);
  }

  if (actionsElem) {
    actionsElem.innerHTML = `<span style="font-size:12px; color:#64748b; font-weight:600;">Processed</span>`;
  }
}

function batchApproveClaims() {
  const pendingBadges = document.querySelectorAll('#pendingClaimsTableBody .claims-status-pill.pending');
  pendingBadges.forEach(b => {
    b.className = 'claims-status-pill approved';
    b.textContent = '● Approved';
  });
  const actionCells = document.querySelectorAll('#pendingClaimsTableBody .claims-actions-cell');
  actionCells.forEach(ac => {
    ac.innerHTML = `<span style="font-size:12px; color:#16a34a; font-weight:700;">✓ Approved</span>`;
  });
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
  closeLeaveModal();
  showToast('Leave request submitted for HR approval.');
}

// Global search handling
function initSearch() {
  const searchInput = document.getElementById('globalSearch');
  if (!searchInput) return;

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const q = searchInput.value.trim();
      if (q) {
        showToast(`Searching for "${q}" across peopleops...`);
      }
    }
  });

  // Shortcut ⌘K / Ctrl+K
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      searchInput.focus();
    }
  });
}

// Toast Alert Utility
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
    setTimeout(() => {
      toast.remove();
    }, 300);
  }, 3500);
}
