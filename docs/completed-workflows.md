# Employee and HR workflows

This branch completes the expense claim, payroll, complaint, grievance, and
in-app notification paths on top of commit `a56a99a`.

## User interfaces

- Employees open **Requests and notifications** in the portal's top bar to
  submit expense claims or grievances, view finalized payroll, and read their
  notification inbox. Complaint history shows the actual status and resolution.
- HR uses **Claims** to decide expense requests; **Payroll** to create periods,
  enter employee lines, and finalize a run; and **Grievance Tracker** to switch
  between complaints and grievances. The bell opens the HR account's own inbox.
- Resolutions are visible to the affected employee. Internal case notes are HR
  only and are omitted from employee API responses.

## Backend contract

| Area | Endpoints | Rules |
| --- | --- | --- |
| Expense claims | `/api/expense-claims/`, `/api/expense-claims/<id>/`, `POST /api/claims/<id>/decision/` | Session-bound ownership, positive amounts, initially Pending; only HR decides Approved/Rejected. Repeating the same decision is safe; a different decision after closure is rejected. |
| Payroll | `/api/payroll-runs/`, `/api/payroll-items/`, `POST /api/payroll-runs/<id>/finalize/` | HR enters base pay and deductions. Backend decimal arithmetic computes net pay. Run finalization closes every write/delete path. Employees see only their own finalized items. |
| Complaints | `/api/complaints/`, `/api/complaints/<id>/` | Open -> In Review -> Resolved/Dismissed. Closing requires a resolution. |
| Grievances | `/api/grievances/`, `/api/grievances/<id>/` | Pending -> Investigating -> In Mediation -> Resolved/Rejected, with HR able to close earlier where appropriate. Closing requires a resolution. |
| Escalation | `POST /api/complaints/<id>/escalate/` | HR explicitly creates one linked grievance. Repeating escalation returns the existing linked record. |
| Inbox | `/api/notifications/`, `PATCH /api/notifications/<id>/read/` | Recipient-only access, including HR; notification preferences are honored. Marking read is idempotent. Targets use allowlisted API detail paths. |

Draft payroll items do not produce posted-payroll alerts. A successful
finalization creates one notification per employee item. Claim and case status
changes create safe notifications without confidential case details or HR notes.
Notification rows participate in the business transaction and roll back with it.

Payroll remains **base pay minus deductions**. Attendance-derived wages,
statutory tax calculations, bank disbursement, and automatic expense reimbursement
are not introduced by this change.

## Migration and compatibility

Back up the target database before applying `python manage.py migrate`.
Migration `0039_complete_workflows` adds case resolution/private-note fields,
an optional complaint-to-grievance link, and optional notification target and
deduplication fields. Existing rows are preserved. Notification target metadata
is optional, so older notifications still render without a detail link.

The pre-existing OnboardingDocument document-type choices differ between the
model and migration history. That unrelated choice drift is not changed here.

## Verification

The Terra implementation agents reported passing focused SQLite suites:

- Four case workflow tests: ownership, HR decisions, private notes, valid state
  changes, mandatory resolutions, escalation idempotency, and inactive users.
- Five payroll workflow tests: decimal calculations, invalid amounts, duplicate
  lines, permissions, draft visibility, finalization, all closed-run mutations,
  and exactly one posted-payroll notification.
- Two new notification tests, plus existing action/overtime/muting checks
  (14 tests in that focused run): rollback, event deduplication, private HR
  inboxes, muted kinds, and idempotent read marking.
- Python syntax, JavaScript syntax, and diff review were performed locally.

The coordinating full-suite run and local demo startup were blocked by automatic
approval review over unverified Visual Studio telemetry egress. They are not
reported as passing. Browser flows have not been verified; repository testing
preferences in `.agents/rules/testing.md` request code/script verification.
PostgreSQL row-lock behavior under concurrency and live Supabase deployment
remain unverified. No production database was migrated.

For an isolated SQLite test run, `scripts/check_workflows_offline.py` configures
`tests.offline_settings` and blocks Python socket connections. Dependencies must
be installed in the selected interpreter; the optional `.testdeps` directory is
local and ignored. This does not control telemetry from the surrounding host.

## Paper alignment after verification

Update the actual results and interface descriptions in Chapter 3 and Section
4.3 to reflect these workflows. Sections 4.1 and 4.2 should account for new case
fields and notification links where their level of detail requires them. Keep
manual payroll inputs distinct from the backend's automatic net-pay calculation.
The Google Doc has not been edited in this implementation checkpoint.
