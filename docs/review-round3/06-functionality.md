# 06 — Functionality deep-dive (@ cf89b71)

Method: traced each view in `pages/dashboard.html` + `static/js/dashboard.js` to `api/urls.py` → `core/views.py`. LIVE = JS fetch hits a routed endpoint; MOCK = static/toast/DOM-only; BROKEN = errors or fake success on use.

| Feature | Verdict | Evidence |
|---|---|---|
| Dashboard KPIs | LIVE | `dashboard.js:1123` GET `api/dashboard-summary/` → `views.py:59` (AllowAny); badge `setApiMode` `:34` |
| Directory | LIVE | `dashboard.js:1157` GET `api/employees/` → `views.py:105`; renders `data-live` cards |
| Onboarding | LIVE | `dashboard.js:281` POST `api/employees/` via `apiFetch` (session+CSRF `:22`) |
| Leave filing | LIVE | `dashboard.js:661` POST `api/leaves/` → `views.py:283`; resolves applicant via live `employeeNameIndex` |
| Clock-in/out | MOCK | zero `attendance/` fetch in JS; `attendance-daily` view is static HTML |
| Shifts | MOCK | `confirmAddStaff :418` DOM-only; label `Allocation (demo) :367`; never touches `shift-rosters/` (`urls.py`) |
| Payroll views | MOCK | zero `payroll-` fetch in JS; endpoints exist (`views.py:303-345`) but unwired |
| Claims (statuses) | LIVE* | `dashboard.js:579/591` GET+POST `api/claim-statuses/` → `views.py:402`; *raw `fetch` (no CSRF) so writes risk 403, unlike `apiFetch` paths |
| Claims (expense/advance) | MOCK | `handleRequestAdvance :643` toast-only; `ExpenseClaimListCreateView (views.py:415)` has **no route** in `api/urls.py` |
| Inbox | LIVE* | `dashboard.js:806` GET + `:871` POST `api/messages/` → `views.py:388`; *same raw-`fetch`/no-CSRF caveat as statuses |
| Audit | MOCK | `filterAuditLogs/exportAuditLogs` client-side filter + hardcoded CSV; never GETs `api/audit-logs/` (`views.py:357` exists) |
| Offboarding | MOCK | `handleOffboardingSubmit :251` toast-only; never DELETEs `api/employees/<uuid>/` (`views.py:166`) |
| Login | LIVE | `dashboard.js:940` POST `api/session-login/` → `views.py:362`; `?next=` bounce `:30` |
| Logout | LIVE | `signOut :1005` POST `api/session-logout/` → `views.py:380` |
| Signup | BROKEN | `handleAuthSignup` toast + redirect only; no POST — reports success without creating anything |

## 'Six live regions' cross-check (Ch.3 §3.4.1)
Claim: KPI summary, directory, onboarding, leave filing, inbox, claim statuses live; attendance/shifts/payroll/audit static + LIVE/DEMO badge. **CONFIRMED EXACT** — the six fetch sites above are the only API reads/writes in `dashboard.js`; the other four views have no fetch and the badge driver (`:34`, loud failure toasts `:1144`) matches the chapter. Narrow reading holds: "claim statuses" (routed) ≠ expense claims (unrouted).
Delta vs round-2 COMPILED: session+CSRF `apiFetch` (`:22`) + `?next=` fix the "JS sends no auth" finding for 5/8 wired paths; messages/claims still use raw `fetch` without CSRF.
