# System Issues and Enhancements

## UI Audit Findings (2026-09-17)

### HR Dashboard (`/hr/`)
**Dead / Non-functional Buttons:**
- **Widget Reordering:** `Move up/down` buttons for dashboard widgets lack handlers.
- **Dashboard Filters:** The `Company` filter button is unbound.
- **Employee Management:** `Cancel`, `Record Promotion`, and `Record Transfer` buttons are unbound.
- **Main Navigation:** Links for Dashboard, Employees, Attendance, Claims, Messages, Logs, and Settings use `href="#"` with no router events.
- **Modals:** The `×` close buttons in popup headers lack event listeners.

**Missing Settings Functions:**
1. **Attendance & Shift Policies:** Grace periods for late arrival, auto-clock-out timeouts, break duration limits.
2. **Leave Policy Configuration:** Leave entitlement quotas, manager approval workflows, carry-forward limits.
3. **Payroll & Loan Limits:** Salary advance max limits, pay cycle schedules, default tax profiles.
4. **Access Control (RBAC):** Permission matrices by role, 2FA toggles, IP range restrictions.
5. **Notification Templates:** Customizable templates for onboarding, grievances, and leave updates.

### Employee Portal (`/employee/`)
**Dead / Non-functional Buttons:**
- **Zero dead buttons found.** All existing tabs and forms are wired correctly.

**Missing Settings Functions:**
*(Currently lacks a settings page entirely. Suggested additions:)*
1. **Profile Management:** Update personal contact details, emergency contacts, and home address.
2. **Security & Authentication:** Change password, manage 2FA devices.
3. **Notification Preferences:** Opt-in/out of alerts (email/SMS) for leave approvals, payroll drops.
4. **Payroll & Bank Details:** Update direct deposit routing information.
5. **App Preferences:** Dark mode/light mode toggles, localization/language preferences.
