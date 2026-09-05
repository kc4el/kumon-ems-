/* ==========================================================================
   Kumon EMS - Interactive Logic & State Management
   ========================================================================== */


document.addEventListener('DOMContentLoaded', () => {
  initBrandLogo();
  initNavigation();
  initSearch();
});

// Automatic Logo Path Resolver for file:// and http:// protocols
function initBrandLogo() {
  const isFileProtocol = window.location.protocol === 'file:';
  const currentPath = window.location.pathname.toLowerCase();
  
  const logoImgs = document.querySelectorAll('.brand-logo-img');
  logoImgs.forEach(img => {
    let bestSrc = '/static/images/kumon-logo.png';
    if (isFileProtocol) {
      if (currentPath.includes('templates') || currentPath.includes('core')) {
        bestSrc = '../../static/images/kumon-logo.png';
      } else {
        bestSrc = 'static/images/kumon-logo.png';
      }
    }
    img.src = bestSrc;
    img.onerror = () => {
      if (img.src.includes('../../static')) {
        img.src = 'static/images/kumon-logo.png';
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
  'profile': { active: 'Profile' },
  'my-details': { active: 'Profile' },
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
    if (txt) txt.textContent = 'Collapse Calendar';
    showToast('Shift Roster Master Calendar expanded.');
  } else {
    cal.classList.add('collapsed');
    if (txt) txt.textContent = 'Expand Calendar';
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
      statusElem.textContent = 'Approved';
    }
    showToast(`Claim ${id} approved for reimbursement settlement.`);
  } else {
    if (statusElem) {
      statusElem.className = 'claims-status-pill rejected';
      statusElem.textContent = 'Rejected';
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
    b.textContent = 'Approved';
  });
  const actionCells = document.querySelectorAll('#pendingClaimsTableBody .claims-actions-cell');
  actionCells.forEach(ac => {
    ac.innerHTML = `<span style="font-size:12px; color:#16a34a; font-weight:700;">Approved</span>`;
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
        showToast(`Searching for "${q}" across Kumon EMS...`);
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

// ==========================================================================
// Messages & Channels Handlers
// ==========================================================================
function filterInboxes(input) {
  const q = input.value.toLowerCase();
  const tiles = document.querySelectorAll('#inboxConversationsList .inbox-user-tile');
  tiles.forEach(tile => {
    const text = tile.textContent.toLowerCase();
    tile.style.display = text.includes(q) ? 'flex' : 'none';
  });
}

function selectChannel(elem, channelKey) {
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
  showToast('Switched to # Company Announcements channel.');
}

function selectInboxUser(elem, userName, initials, userRole, key) {
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
  showToast(`Active chat: ${userName}`);
}

function handleSendChatMessage(e) {
  e.preventDefault();
  const input = document.getElementById('chatTextInput');
  const text = input.value.trim();
  if (!text) return;

  const stream = document.getElementById('chatStreamMessages');
  if (stream) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const row = document.createElement('div');
    row.className = 'chat-msg-row outgoing';
    row.innerHTML = `
      <div class="chat-bubble outgoing">
        <p>${escapeHtml(text)}</p>
        <span class="chat-time-stamp outgoing-stamp">${timeStr} • Sent</span>
      </div>
    `;
    stream.appendChild(row);
    stream.scrollTop = stream.scrollHeight;
  }

  input.value = '';
  showToast('Message sent.');
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ==========================================================================
// Authentication Screen & Navigation Handlers
// ==========================================================================
function switchAuthPage(mode) {
  const loginCard = document.getElementById('authScreenLogin');
  const signupCard = document.getElementById('authScreenSignup');
  const tabLogin = document.getElementById('tabBtnLogin');
  const tabSignup = document.getElementById('tabBtnSignup');

  if (loginCard && signupCard) {
    loginCard.style.display = (mode === 'login' ? 'block' : 'none');
    signupCard.style.display = (mode === 'signup' ? 'block' : 'none');
  }

  if (tabLogin && tabSignup) {
    if (mode === 'login') {
      tabLogin.classList.add('active');
      tabSignup.classList.remove('active');
    } else {
      tabSignup.classList.add('active');
      tabLogin.classList.remove('active');
    }
  }

  if (window.history && window.history.replaceState) {
    window.history.replaceState(null, '', `#${mode}`);
  }
}

function openAuthModal(mode = 'login') {
  // If dedicated login page is preferred or fallback modal exists
  const modal = document.getElementById('authModal');
  if (modal) {
    modal.classList.add('active');
    switchAuthMode(mode);
  } else {
    navigateToLogin(mode);
  }
}

function closeAuthModal() {
  const modal = document.getElementById('authModal');
  if (modal) modal.classList.remove('active');
}

function switchAuthMode(mode) {
  const loginC = document.getElementById('authLoginContainer');
  const signupC = document.getElementById('authSignupContainer');
  if (loginC && signupC) {
    loginC.style.display = (mode === 'login' ? 'block' : 'none');
    signupC.style.display = (mode === 'signup' ? 'block' : 'none');
  }
}

function switchAuthPage(mode = 'login') {
  const loginCard = document.getElementById('authScreenLogin');
  const signupCard = document.getElementById('authScreenSignup');

  if (loginCard && signupCard) {
    if (mode === 'signup') {
      loginCard.style.display = 'none';
      signupCard.style.display = 'block';
      window.location.hash = 'signup';
      document.title = 'Employee Registration • Kumon EMS';
    } else {
      signupCard.style.display = 'none';
      loginCard.style.display = 'block';
      window.location.hash = 'login';
      document.title = 'Portal Authentication • Kumon EMS';
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
  const empId = document.getElementById('loginEmployeeId')?.value || 'Marcus Williams';
  showToast(`Welcome back, ${empId}! Authenticated to Kumon EMS.`);
  sessionStorage.setItem('kumon_ems_auth_user', empId);

  const authScreen = document.getElementById('authScreenContainer');
  if (authScreen) authScreen.classList.add('authenticated');
  closeAuthModal();

  // If on standalone login page, redirect to dashboard/index
  const currentPath = window.location.pathname.toLowerCase();
  const isFileProtocol = window.location.protocol === 'file:';

  if (isFileProtocol || currentPath.includes('login') || currentPath.includes('auth') || currentPath.includes('signup')) {
    setTimeout(() => {
      if (isFileProtocol || currentPath.endsWith('.html')) {
        window.location.href = 'dashboard.html';
      } else {
        window.location.href = '/';
      }
    }, 400);
  } else {
    switchView('dashboard');
  }
}

function handleAuthSignup(e) {
  if (e) e.preventDefault();
  const empId = document.getElementById('signupEmployeeId')?.value || 'New Employee';
  showToast(`Account registered successfully! Welcome to Kumon EMS, ${empId}.`);
  sessionStorage.setItem('kumon_ems_auth_user', empId);

  const authScreen = document.getElementById('authScreenContainer');
  if (authScreen) authScreen.classList.add('authenticated');
  closeAuthModal();

  const currentPath = window.location.pathname.toLowerCase();
  const isFileProtocol = window.location.protocol === 'file:';

  if (isFileProtocol || currentPath.includes('login') || currentPath.includes('auth') || currentPath.includes('signup')) {
    setTimeout(() => {
      if (isFileProtocol || currentPath.endsWith('.html')) {
        window.location.href = 'dashboard.html';
      } else {
        window.location.href = '/';
      }
    }, 400);
  } else {
    switchView('dashboard');
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
  sessionStorage.removeItem('kumon_ems_auth_user');


  const authScreen = document.getElementById('authScreenContainer');
  if (authScreen) {
    authScreen.classList.remove('authenticated');
    switchAuthPage('login');
  } else {
    setTimeout(() => {
      navigateToLogin('login');
    }, 400);
  }
}


