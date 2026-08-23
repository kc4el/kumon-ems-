/* ==========================================================================
   peopleops / Northstar Studio (Kumon EMS) - Interactive Application Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initSearch();
});

// View Navigation Mapping
const viewBreadcrumbs = {
  'dashboard': { root: 'Northstar Studio', active: 'Overview' },
  'employee-directory': { root: 'Northstar Studio / Workspace', active: 'Employee Directory' },
  'employee-manage': { root: 'Northstar Studio / Employees', active: 'Manage Staff' },
  'employee-grievance': { root: 'Northstar Studio / Employees', active: 'Grievance Tracker' },
  'attendance-daily': { root: 'Northstar Studio / Workspace', active: 'Daily Attendance & Time Log' },
  'attendance-shift': { root: 'Northstar Studio / Operations', active: 'Shift Scheduling & Roster' },
  'attendance-leave': { root: 'Northstar Studio / Workspace', active: 'Leave & Absence Management' },
  'payroll': { root: 'Northstar Studio / Operations', active: 'Payroll Ledger' },
  'my-details': { root: 'Northstar Studio / Portal', active: 'My Details' },
  'claims': { root: 'Northstar Studio / Portal', active: 'Expense Claims' },
  'reports': { root: 'Northstar Studio / Manage', active: 'Reports & Analytics' }
};

function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetView = item.getAttribute('data-view');
      if (targetView) {
        switchView(targetView);
      }
    });
  });
}

function switchView(viewName) {
  // Update sidebar active link
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.getAttribute('data-view') === viewName || 
       (viewName.startsWith('employee') && item.getAttribute('data-view') === 'employee-directory') ||
       (viewName.startsWith('attendance') && item.getAttribute('data-view') === 'attendance-daily' && viewName !== 'attendance-leave') ||
       (viewName === 'attendance-leave' && item.getAttribute('data-view') === 'attendance-leave')) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
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

  // Update breadcrumb
  const crumbRoot = document.querySelector('.crumb-root');
  const currentCrumb = document.getElementById('currentCrumb');
  if (viewBreadcrumbs[viewName]) {
    if (crumbRoot) crumbRoot.textContent = viewBreadcrumbs[viewName].root;
    if (currentCrumb) currentCrumb.textContent = viewBreadcrumbs[viewName].active;
  }

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Accordion toggle for Employee Directory
function toggleAccordion(summaryElement) {
  const card = summaryElement.closest('.employee-accordion-card');
  const indicator = summaryElement.querySelector('.toggle-indicator');
  
  if (card.classList.contains('open')) {
    card.classList.remove('open');
    if (indicator) indicator.textContent = '▼ Expand Profile';
  } else {
    card.classList.add('open');
    if (indicator) indicator.textContent = '▲ Collapse Profile';
  }
}

// Filter Employee Directory
function filterDirectory() {
  const dept = document.getElementById('deptFilter').value.toLowerCase();
  const role = document.getElementById('roleFilter').value.toLowerCase();
  const status = document.getElementById('statusFilter').value.toLowerCase();

  const cards = document.querySelectorAll('#employeeRosterList .employee-accordion-card');
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
      const q = searchInput.value.trim().toLowerCase();
      if (q) {
        showToast(`Searching for "${q}" across directory and records...`);
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
