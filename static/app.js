/*
 * peopleops / Kumon EMS
 * Dashboard interaction and same-origin API integration.
 */

const API_BASE = '/api';
const appState = {
  employees: [],
  departments: [],
  attendance: [],
  leaves: [],
};

const viewBreadcrumbs = {
  dashboard: { root: 'Northstar Studio', active: 'Overview' },
  'employee-directory': { root: 'Northstar Studio / Workspace', active: 'Employee Directory' },
  'employee-manage': { root: 'Northstar Studio / Employees', active: 'Manage Staff' },
  'employee-grievance': { root: 'Northstar Studio / Employees', active: 'Grievance Tracker' },
  'attendance-daily': { root: 'Northstar Studio / Workspace', active: 'Daily Attendance & Time Log' },
  'attendance-shift': { root: 'Northstar Studio / Operations', active: 'Shift Scheduling & Roster' },
  'attendance-leave': { root: 'Northstar Studio / Workspace', active: 'Leave & Absence Management' },
  payroll: { root: 'Northstar Studio / Operations', active: 'Payroll Ledger' },
  'my-details': { root: 'Northstar Studio / Portal', active: 'My Details' },
  claims: { root: 'Northstar Studio / Portal', active: 'Expense Claims' },
  reports: { root: 'Northstar Studio / Manage', active: 'Reports & Analytics' },
};

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initSearch();
  refreshLiveData();
});

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
    ...options,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    // A non-JSON error response is handled using the status text below.
  }

  if (!response.ok) {
    const message = payload?.error || payload?.detail || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

function asList(payload) {
  return Array.isArray(payload) ? payload : payload?.results || [];
}

async function refreshLiveData() {
  try {
    const [summary, employees, departments, attendance, leaves] = await Promise.all([
      apiRequest('/dashboard-summary/'),
      apiRequest('/employees/'),
      apiRequest('/departments/'),
      apiRequest('/attendance/'),
      apiRequest('/leaves/'),
    ]);

    appState.employees = asList(employees);
    appState.departments = asList(departments);
    appState.attendance = asList(attendance);
    appState.leaves = asList(leaves);

    renderDashboardSummary(summary);
    renderEmployeeDirectory();
    renderDashboardAttendance();
    renderLeaveRegister();
    populateEmployeeSelects();
    populateDepartmentSelect();
  } catch (error) {
    console.error('Unable to load dashboard data:', error);
    showToast(`Live data could not be loaded: ${error.message}`);
  }
}

function initNavigation() {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', (event) => {
      event.preventDefault();
      const targetView = item.getAttribute('data-view');
      if (targetView) switchView(targetView);
    });
  });
}

function switchView(viewName) {
  document.querySelectorAll('.nav-item').forEach((item) => {
    const isSelected =
      item.getAttribute('data-view') === viewName ||
      (viewName.startsWith('employee') && item.getAttribute('data-view') === 'employee-directory') ||
      (viewName.startsWith('attendance') && item.getAttribute('data-view') === 'attendance-daily' && viewName !== 'attendance-leave') ||
      (viewName === 'attendance-leave' && item.getAttribute('data-view') === 'attendance-leave');
    item.classList.toggle('active', isSelected);
  });

  document.querySelectorAll('.view-panel').forEach((panel) => panel.classList.remove('active'));
  const targetPanel = document.getElementById(`view-${viewName}`);
  if (targetPanel) {
    targetPanel.classList.add('active');
  } else {
    const placeholderPanel = document.getElementById('view-placeholder');
    const placeholderTitle = document.getElementById('placeholderTitle');
    if (placeholderPanel && placeholderTitle) {
      placeholderTitle.textContent = viewName.replaceAll('-', ' ').toUpperCase();
      placeholderPanel.classList.add('active');
    }
  }

  const breadcrumb = viewBreadcrumbs[viewName];
  if (breadcrumb) {
    const crumbRoot = document.querySelector('.crumb-root');
    const currentCrumb = document.getElementById('currentCrumb');
    if (crumbRoot) crumbRoot.textContent = breadcrumb.root;
    if (currentCrumb) currentCrumb.textContent = breadcrumb.active;
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderDashboardSummary(summary) {
  setText('dashboardTotalEmployees', summary.total_employees ?? 0);
  setText('dashboardActiveEmployees', summary.active_employees ?? 0);
  setText('dashboardApprovedLeaves', summary.approved_leaves ?? 0);
  setText('dashboardPendingLeaves', summary.pending_leaves ?? 0);
}

function renderEmployeeDirectory() {
  const container = document.getElementById('employeeRosterList');
  if (!container) return;

  if (!appState.employees.length) {
    container.innerHTML = emptyState('No employee profiles are available yet.');
    return;
  }

  const departmentMap = new Map(appState.departments.map((department) => [String(department.id), department.name]));
  const onLeaveEmployeeIds = new Set(
    appState.leaves
      .filter((leave) => String(leave.status || '').toLowerCase() === 'approved')
      .map((leave) => String(leave.employee_id || leave.employee || '')),
  );

  container.innerHTML = appState.employees
    .map((employee) => {
      const department = departmentName(employee, departmentMap);
      const status = onLeaveEmployeeIds.has(String(employee.id))
        ? 'On Leave'
        : employee.is_active === false
          ? 'Inactive'
          : 'Active';
      const statusClass = status === 'On Leave' ? 'badge-warning' : status === 'Inactive' ? 'badge-danger' : 'badge-success';
      const name = employeeName(employee);
      const hiredDate = employee.date_hired ? formatDate(employee.date_hired) : 'Not recorded';

      return `
        <article class="employee-accordion-card" data-dept="${escapeAttribute(department)}" data-role="employee" data-status="${escapeAttribute(status)}">
          <button type="button" class="card-summary" aria-expanded="false" onclick="toggleAccordion(this)">
            <span class="employee-identity">
              <span class="id-icon" aria-hidden="true">📇</span>
              <span class="emp-name">${escapeHtml(name)}</span>
              <span class="emp-role">Employee • ${escapeHtml(department)}</span>
            </span>
            <span class="summary-meta">
              <span class="badge ${statusClass}">${escapeHtml(status)}</span>
              <span class="toggle-indicator">▼ Expand Profile</span>
            </span>
          </button>
          <div class="card-details">
            <div class="detail-columns-grid">
              <div class="detail-col">
                <span class="detail-heading">CONTACT</span>
                <div class="detail-row"><span class="detail-ico">✉</span> ${escapeHtml(employee.email || 'Not recorded')}</div>
              </div>
              <div class="detail-col">
                <span class="detail-heading">EMPLOYMENT & ORG DETAILS</span>
                <div class="detail-row"><span class="detail-ico">🏢</span> ${escapeHtml(department)}</div>
                <div class="detail-row"><span class="detail-ico">📅</span> Hired ${escapeHtml(hiredDate)}</div>
              </div>
              <div class="detail-col">
                <span class="detail-heading">RECORD STATUS</span>
                <div class="perf-rating">Employee ID: <strong>${escapeHtml(String(employee.id || '—'))}</strong></div>
              </div>
            </div>
          </div>
        </article>`;
    })
    .join('');

  filterDirectory();
}

function renderDashboardAttendance() {
  const body = document.getElementById('dashboardAttendanceBody');
  if (!body) return;

  const employeesById = new Map(appState.employees.map((employee) => [String(employee.id), employee]));
  const departmentMap = new Map(appState.departments.map((department) => [String(department.id), department.name]));
  const recentRecords = appState.attendance.slice(0, 6);

  if (!recentRecords.length) {
    body.innerHTML = emptyTableRow(5, 'No attendance records are available.');
    return;
  }

  body.innerHTML = recentRecords
    .map((record) => {
      const employee = employeesById.get(String(record.employee_id || record.employee || '')) || {};
      const checkedOut = Boolean(record.clock_out);
      const name = employeeName(employee) || 'Unknown employee';
      const department = departmentName(employee, departmentMap);
      return `
        <tr>
          <td class="font-bold">${escapeHtml(name)}</td>
          <td>${escapeHtml(department)}</td>
          <td>Employee</td>
          <td><span class="badge ${checkedOut ? 'badge-purple' : 'badge-success'}">${checkedOut ? 'Clocked out' : 'Present'}</span></td>
          <td>${escapeHtml(formatTime(record.clock_in))}</td>
        </tr>`;
    })
    .join('');
}

function renderLeaveRegister() {
  const body = document.getElementById('leaveRegisterTableBody');
  if (!body) return;

  const employeesById = new Map(appState.employees.map((employee) => [String(employee.id), employee]));
  const departmentMap = new Map(appState.departments.map((department) => [String(department.id), department.name]));

  if (!appState.leaves.length) {
    body.innerHTML = emptyTableRow(5, 'No leave requests are available.');
    return;
  }

  body.innerHTML = appState.leaves
    .map((leave) => {
      const employee = employeesById.get(String(leave.employee_id || leave.employee || '')) || {};
      const status = leave.status || 'Pending';
      const statusClass = leaveStatusClass(status);
      const start = formatDate(leave.start_date);
      const end = formatDate(leave.end_date);
      const employeeDescription = `${departmentName(employee, departmentMap)} department`;
      return `
        <tr>
          <td>
            <div class="emp-row-title">${escapeHtml(employeeName(employee) || 'Unknown employee')}</div>
            <div class="emp-row-sub">${escapeHtml(employeeDescription)}</div>
          </td>
          <td><span class="pill-type pill-type-blue">${escapeHtml(leaveType(leave.reason))}</span></td>
          <td>
            <div class="duration-main">${escapeHtml(durationLabel(leave.start_date, leave.end_date))}</div>
            <div class="duration-sub">${escapeHtml(`${start} – ${end}`)}</div>
          </td>
          <td>${escapeHtml(formatDate(leave.created_at || leave.start_date))}</td>
          <td><span class="badge ${statusClass}">${escapeHtml(status)}</span></td>
        </tr>`;
    })
    .join('');
}

function populateEmployeeSelects() {
  const select = document.getElementById('leaveEmployee');
  if (!select) return;

  const currentValue = select.value;
  select.innerHTML = '<option value="">Select an employee</option>';
  appState.employees
    .filter((employee) => employee.is_active !== false)
    .forEach((employee) => {
      const option = document.createElement('option');
      option.value = employee.id;
      option.textContent = employeeName(employee);
      select.appendChild(option);
    });
  select.value = currentValue;
}

function populateDepartmentSelect() {
  const select = document.getElementById('onboardingDepartment');
  if (!select) return;

  const currentValue = select.value;
  select.innerHTML = '<option value="">Select a department</option>';
  appState.departments.forEach((department) => {
    const option = document.createElement('option');
    option.value = department.id;
    option.textContent = department.name;
    select.appendChild(option);
  });
  select.value = currentValue;
}

function toggleAccordion(summaryElement) {
  const card = summaryElement.closest('.employee-accordion-card');
  const indicator = summaryElement.querySelector('.toggle-indicator');
  const isOpen = card.classList.toggle('open');
  summaryElement.setAttribute('aria-expanded', String(isOpen));
  if (indicator) indicator.textContent = isOpen ? '▲ Collapse Profile' : '▼ Expand Profile';
}

function filterDirectory() {
  const departmentFilter = (document.getElementById('deptFilter')?.value || 'all').toLowerCase();
  const roleFilter = (document.getElementById('roleFilter')?.value || 'all').toLowerCase();
  const statusFilter = (document.getElementById('statusFilter')?.value || 'all').toLowerCase();

  document.querySelectorAll('#employeeRosterList .employee-accordion-card').forEach((card) => {
    const department = (card.dataset.dept || '').toLowerCase();
    const role = (card.dataset.role || '').toLowerCase();
    const status = (card.dataset.status || '').toLowerCase();
    const visible =
      (departmentFilter === 'all' || department === departmentFilter) &&
      (roleFilter === 'all' || role === roleFilter) &&
      (statusFilter === 'all' || status === statusFilter || (statusFilter === 'present today' && status === 'active'));
    card.style.display = visible ? 'block' : 'none';
  });
}

async function handleOnboarding(event) {
  event.preventDefault();
  const name = document.getElementById('onboardingName').value.trim();
  const email = document.getElementById('onboardingEmail').value.trim();
  const departmentId = document.getElementById('onboardingDepartment').value;
  const startDate = document.getElementById('onboardingStartDate').value;
  const nameParts = name.split(/\s+/).filter(Boolean);

  if (nameParts.length < 2) {
    showToast('Please enter both a first and last name.');
    return;
  }

  try {
    await apiRequest('/employees/', {
      method: 'POST',
      body: JSON.stringify({
        first_name: nameParts.shift(),
        last_name: nameParts.join(' '),
        email,
        department_id: departmentId,
      }),
    });
    event.target.reset();
    showToast('Employee profile created successfully.');
    await refreshLiveData();
    switchView('employee-directory');
  } catch (error) {
    showToast(`Employee could not be created: ${error.message}`);
  }
}

function openLeaveModal() {
  document.getElementById('leaveModal')?.classList.add('active');
}

function closeLeaveModal() {
  document.getElementById('leaveModal')?.classList.remove('active');
}

async function handleApplyLeave(event) {
  event.preventDefault();
  const employeeId = document.getElementById('leaveEmployee').value;
  const leaveTypeValue = document.getElementById('leaveType').value;
  const startDate = document.getElementById('leaveStartDate').value;
  const endDate = document.getElementById('leaveEndDate').value;
  const reason = document.getElementById('leaveReason').value.trim();

  if (endDate < startDate) {
    showToast('The leave end date cannot be earlier than the start date.');
    return;
  }

  try {
    await apiRequest('/leaves/', {
      method: 'POST',
      body: JSON.stringify({
        employee_id: employeeId,
        leave_type: leaveTypeCode(leaveTypeValue),
        start_date: startDate,
        end_date: endDate,
        reason: `${leaveTypeValue}: ${reason}`,
        status: 'pending',
      }),
    });
    event.target.reset();
    closeLeaveModal();
    showToast('Leave request submitted for review.');
    await refreshLiveData();
  } catch (error) {
    showToast(`Leave request could not be submitted: ${error.message}`);
  }
}

function setPtMode(mode) {
  const promoteButton = document.getElementById('btnModePromote');
  const transferButton = document.getElementById('btnModeTransfer');
  const title = document.getElementById('ptCardTitle');
  const subtitle = document.getElementById('ptCardSubtitle');
  const promoteContainer = document.getElementById('promoteFormContainer');
  const transferContainer = document.getElementById('transferFormContainer');
  const isPromote = mode === 'promote';

  promoteButton?.classList.toggle('active', isPromote);
  transferButton?.classList.toggle('active', !isPromote);
  if (title) title.textContent = isPromote ? 'Promote Employee' : 'Transfer employee';
  if (subtitle) {
    subtitle.textContent = isPromote
      ? 'Record the next role and pay-grade step with a clear effective date and promotion rationale.'
      : 'Move a person to a new team or work location and keep the effective date and rationale on the record.';
  }
  if (promoteContainer) promoteContainer.style.display = isPromote ? 'block' : 'none';
  if (transferContainer) transferContainer.style.display = isPromote ? 'none' : 'block';
}

function initSearch() {
  const searchInput = document.getElementById('globalSearch');
  if (!searchInput) return;

  searchInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    const query = searchInput.value.trim().toLowerCase();
    if (!query) return;
    switchView('employee-directory');
    document.querySelectorAll('#employeeRosterList .employee-accordion-card').forEach((card) => {
      card.style.display = card.textContent.toLowerCase().includes(query) ? 'block' : 'none';
    });
  });

  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      searchInput.focus();
    }
  });
}

function employeeName(employee) {
  return [employee?.first_name, employee?.last_name].filter(Boolean).join(' ') || employee?.name || '';
}

function departmentName(employee, departmentMap) {
  const reference = employee?.department_id || employee?.department;
  if (typeof reference === 'object' && reference?.name) return reference.name;
  return employee?.department_name || departmentMap?.get(String(reference)) || 'Unassigned';
}

function leaveType(reason) {
  const value = String(reason || 'Leave request');
  const separator = value.indexOf(':');
  return separator > 0 ? value.slice(0, separator) : 'Leave request';
}

function leaveTypeCode(label) {
  const codes = {
    'Annual Vacation': 'vacation',
    'Medical / Sick Leave': 'sick',
    'Casual Leave': 'personal',
    'Parental Leave': 'parental',
    'Emergency Personal': 'personal',
    'Compensatory Off': 'personal',
  };
  return codes[label] || 'personal';
}

function durationLabel(start, end) {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return 'Date not available';
  const days = Math.floor((endDate - startDate) / 86400000) + 1;
  return `${Math.max(days, 1)} calendar day${days === 1 ? '' : 's'}`;
}

function leaveStatusClass(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'approved' || normalized === 'accepted') return 'badge-success';
  if (normalized === 'rejected' || normalized === 'denied') return 'badge-danger';
  return 'badge-warning';
}

function formatDate(value) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatTime(value) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function emptyState(message) {
  return `<div class="empty-state" role="status">${escapeHtml(message)}</div>`;
}

function emptyTableRow(columnCount, message) {
  return `<tr><td colspan="${columnCount}" class="text-muted-sm">${escapeHtml(message)}</td></tr>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll('`', '&#096;');
}

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
