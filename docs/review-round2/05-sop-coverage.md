# SOP coverage re-grade (round 2, code @ c8690ed) + Chapter 3 corrections

Note: round-1 review used its own SOP numbering (lifecycle/shifts/UX); below uses the
Ch.1 numbering per brief: S1 dashboard, S2 attendance+payroll, S3 shifts+notifications,
S4 safety+UX, S5 resignation+30-day deletion.

## Verdict table (current code)

| SOP | Verdict | Evidence |
|---|---|---|
| S1 centralized dashboard (attendance/salary/performance/leaves) | COVERED | `DashboardSummaryView` (`core/views.py:51`), route `api/urls.py:28`; all CRUD routes `api/urls.py:30-97`; live wiring `static/js/dashboard.js:952` (summary), `:983` (directory), `:258` (onboard POST), `:601` (leave POST) |
| S2 attendance verification + payroll accuracy | COVERED | `unique_together (employee,date)` (`core/models.py:49`); dup guard (`core/serializers.py:44-49`); race → 409 (`core/views.py:165-170`); clock-out binds open record or 404 (`core/views.py:178-…`); `PayrollRun/Item` persisted per period (`core/models.py:78-94`) — no auto attendance→payroll computation |
| S3 shift scheduling + conflict detection + real-time notifications | PARTIAL | Scheduling FIXED: `ShiftRoster.employee` FK + `work_date` (`core/models.py:66-69`, mig `0006`); overlap validator (`core/serializers.py:75-100`). Notifications MISSING: zero model/endpoint/client code (grep `notif*` hits nothing outside vendored pkgs) |
| S4 data safety/privacy + minimal-click UX | PARTIAL | Safety COVERED: server-side Supabase create + `delete_user` rollback (`core/views.py:119-148`); token endpoint (`api/urls.py:98`); global `IsAuthenticated` (`kumon_ems/settings.py:167`, public summary excepted `core/views.py:55`); audit signals + read-only `audit-logs/` (`core/signals.py`, `api/urls.py:97`). UX PARTIAL: only dashboard/employees/leaves fetch live; shift/payroll/performance/attendance views still static/toast-only (no other `fetch(` in `dashboard.js`) |
| S5 resignation + 30-day auto-deletion | PARTIAL (was MISSING) | Soft-resign on DELETE (`is_active=False` + `resigned_at`, `core/views.py:155-158`); `purge_resigned --days 30 --dry-run` (`core/management/commands/purge_resigned.py:13-34`, tests `core/tests.py:114-153`). BUT: no scheduler (no cron/celery anywhere) and no UI trigger — manual command only |

## Chapter-claim corrections (`docs/chapter3/CHAPTER3.md`)

Newly TRUE (round-1 gaps closed, chapter already claims or implies them):
- §3.4.3 "assign employees across shift_types" — true since FK/`work_date` added (§3.2/Fig.2 text predates fix but now holds).
- §3.4.2 duplicate/clock-out flow — true at backend level (guards + 409 + 404 paths exist).
- §3.4.4 server-side Supabase + rollback + audit trail — true (`views.py:119-148`, `signals.py`, `audit-logs/`).
- §3.4.5 two-stage offboarding (deactivate → erase after 30d) — true in spirit via `perform_destroy` + `purge_resigned`.

Still FALSE / overstated:
- §3.4.5 "erasure via `DELETE employees/<uuid:pk>/`" — FALSE: that endpoint now soft-deactivates (`views.py:155-158`); erasure is the `purge_resigned` command, which the chapter never names.
- §3.4.5 "window enforced as operational retention policy" — understates the gap: purge exists but is UNSCHEDULED (no cron/Celery config in repo); auto-deletion is not automatic.
- §3.4.2 flowchart "422 ValidationError" — wrong code: serializer dup → 400, race dup → 409 (`views.py:169-170`, `core/exceptions.py:7`); "airtight" overstates — payroll is manually posted, never derived from attendance.
- §3.4.3 flowchart "roster adjusted for absence" loop — overstated: no code links leave approval to rosters; coordination is manual side-by-side CRUD.
- §3.4.4 "tamper-evident history" — overstated: `EmployeeAuditLog` is a plain writable table, no immutability constraint.

Newly missing from the chapter (code exists, or gap unacknowledged):
- Token auth + `IsAuthenticated` default + public-summary exception — unmentioned in §§3.2/3.4.4 (`api/urls.py:98`, `settings.py:167`, `views.py:55`).
- Shift-overlap validator — unmentioned in §3.4.3 (`serializers.py:75-100`).
- `purge_resigned` command, `--days/--dry-run`, unscheduled status — unmentioned in §3.4.5.
- SOP3 notifications half — absent from BOTH code and §3.4.3 (chapter silent on the gap).
- Frontend wiring state — unclaimed anywhere: dashboard/employees/leaves live, shift/payroll/performance/attendance still static.
