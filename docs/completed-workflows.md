# Employee and HR workflows

This document describes the expense claim, complaint, grievance, and in-app
notification workflows, alongside the legacy payroll records. Pay estimates
are described in [pay-estimates.md](pay-estimates.md).

## User interfaces

- Employees open **Requests and notifications** in the portal's top bar to
  submit expense claims or grievances and read their notification inbox. Complaint history shows the actual status and resolution.
- HR uses **Claims** to decide expense requests; **Pay Estimates** for system-generated estimates; and **Grievance Tracker** to switch
  between complaints and grievances. The bell opens the HR account's own inbox.
- Resolutions are visible to the affected employee. Internal case notes are HR
  only and are omitted from employee API responses.

## Backend contract

| Area | Endpoints | Rules |
| --- | --- | --- |
| Expense claims | `/api/expense-claims/`, `/api/expense-claims/<id>/`, `POST /api/claims/<id>/decision/` | Session-bound ownership, positive amounts, initially Pending; only HR decides Approved/Rejected. Repeating the same decision is safe; a different decision after closure is rejected. |
| Legacy payroll | `/api/payroll-runs/`, `/api/payroll-items/`, `POST /api/payroll-runs/<id>/finalize/` | HR-only read and write. Existing records are preserved; finalization closes every write/delete path. These records are separate from pay estimates. |
| Complaints | `/api/complaints/`, `/api/complaints/<id>/` | Open -> In Review -> Resolved/Dismissed. Closing requires a resolution. |
| Grievances | `/api/grievances/`, `/api/grievances/<id>/` | Pending -> Investigating -> In Mediation -> Resolved/Rejected, with HR able to close earlier where appropriate. Closing requires a resolution. |
| Escalation | `POST /api/complaints/<id>/escalate/` | HR explicitly creates one linked grievance. Repeating escalation returns the existing linked record. |
| Inbox | `/api/notifications/`, `PATCH /api/notifications/<id>/read/` | Recipient-only access, including HR; notification preferences are honored. Marking read is idempotent. Targets use allowlisted API detail paths. |

Legacy payroll finalization does not send employees a payroll-posted notice.
Older payroll-posted notices are hidden from employee inboxes without deleting
historical records; attendance-related overtime notices remain available. Claim
and case status changes create notifications without confidential case details
or HR notes. Notification rows participate in their business transaction.

Pay estimates support HR review only and do not calculate statutory tax, disburse
funds, or automatically reimburse expenses. The actual pay handler is responsible
for validating and processing pay.

## Migration and compatibility

Back up the target database before applying `python manage.py migrate`.
Migration `0039_complete_workflows` adds case resolution/private-note fields,
an optional complaint-to-grievance link, and optional notification target and
deduplication fields. Existing rows are preserved. Notification target metadata
is optional, so older notifications still render without a detail link.

Migration `0040` adds pay estimate records. No production database was migrated.

The pre-existing OnboardingDocument document-type choices differ between the
model and migration history. That unrelated choice drift is not changed here.

## Historical verification

The following reports describe the earlier workflow implementation, before the
HR-only pay estimate changes. They are not validation of the current contract.
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
fields and notification links where their level of detail requires them. Describe pay estimates as HR review aids distinct from actual pay processing.
The Google Doc has not been edited in this implementation checkpoint.
