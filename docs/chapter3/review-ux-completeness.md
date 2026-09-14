# Review C — UX & Completeness vs SOPs (chore/standard-format)

Evidence: `core/templates/core/index.html` (4061 lines), `core/templates/core/login.html`,
`static/js/dashboard.js` (839 lines, zero `fetch(` calls), `api/urls.py`, `core/views.py`,
`core/models.py`, `core/serializers.py`, README workflow table.

## SOP verdicts

- **SOP1 Unified dashboard — COVERED.** `GET /api/dashboard-summary/` + employees/departments/
  attendance/leaves wired per README table; hero + pulse cards in `index.html` (~L120-200).
- **SOP2 Employee lifecycle (onboard/offboard) — PARTIAL.** Onboarding modal (`#onboardingModal`,
  L3821) + `POST /api/employees/` exist, but `handleOnboarding()` (dashboard.js L245) only fires
  `showToast(...)` — no POST. Offboarding wizard has resignation options (index.html L1210) but
  `handleOffboardingSubmit()` (L215) is toast-only; no resignation endpoint in `api/urls.py`.
- **SOP3 Shift coordination + notifications — PARTIAL.** `GET/POST /api/shift-rosters/` CRUD exists,
  but no conflict/overlap detection (ShiftRoster has no employee/date fields, no `clean()`; only
  Attendance has `unique_together`). Notifications = header bell firing a hardcoded toast (L103-104).
- **SOP4 Minimal-click UX — PARTIAL.** Sidebar `switchView()`, breadcrumbs, search/filter work for
  claims (`filterClaimsTable`), inbox (`filterInboxes`), audit logs (`filterAuditLogs`) — all
  client-side DOM filtering, no server query. No employee-directory search input found.
- **SOP5 Retention / 30-day deletion — MISSING.** No deletion-confirm UI, no retention endpoint;
  `EmployeeDetailView` is generic DRF destroy with no 30-day grace logic; only "Retention" label
  (index.html L206) and "30 Calendar Days" leave-balance text (L2362).

## Cross-cutting issues

1. **Auth redundancy:** `/login/`, `/signup/`, `/auth/` all map to `login_view` (core/urls.py L7-9);
   signup is a JS card toggle (`switchAuthPage`), `handleAuthLogin/Signup` use sessionStorage toasts
   + redirect — no real backend auth call.
2. **Same-origin fetch gap:** README claims same-origin API consumption, but `dashboard.js` and
   `index.html` contain zero `fetch(`/XHR calls — all handlers mutate DOM + `showToast`. Dashboard
   renders static demo data; only `pages/` previews aside, live binding is unwired.
3. **Modal pattern inconsistent:** leave/advance modals use `.active` class; onboarding uses inline
   `display:flex` — unify + wire all three to POST (`/api/employees/`, `/api/leaves/`).
4. **Recommend:** add shift-overlap validator, notification model/endpoint, resignation endpoint +
   30-day soft-delete UI, employee search input, real login POST; dedupe `/signup`→redirect or
   separate view.
