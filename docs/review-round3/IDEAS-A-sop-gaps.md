# IDEAS-A — SOP-Gap Features (close PARTIAL verdicts)

Scope: chore/standard-format @ cf89b71. Sources: COMPILED.md, JUSTIFICATION-AND-IMPROVEMENTS.md.

## A1. Leave→Roster auto-block
- Problem: approved leave never touches roster; §3.4.3 "roster adjusted" is false (P-findings §3.4.3, Justif #14).
- Proposal: `Shift.status=on_leave` set by `Leave.approve()` in one txn; `GET /api/roster/?date=` excludes blocked shifts; roster cell shows "On leave" badge.
- Value: flips S3-scheduling claim from OVERSTATED to COVERED.
- Effort: S

## A2. SOP3 notifications (leave/shift decisions)
- Problem: zero notification model/endpoint/client; S3 graded PARTIAL (COMPILED #21, Justif #14).
- Proposal: `Notification(recipient, kind, ref_id, read_at)` + `GET/PATCH /api/notifications/`; bell icon in dashboard header with unread count.
- Value: flips S3-notifications from MISSING to COVERED.
- Effort: M

## A3. Attendance→Payroll derivation
- Problem: payroll manually posted, never derived; PATCH without base_pay 500s (COMPILED #5 C3/P2).
- Proposal: `PayrollRun.derive(month)` sums approved attendance×rate server-side; `POST /api/payroll/derive/`; payroll table gains "Derived/Period" columns.
- Value: flips S2-payroll from manual-post to COVERED.
- Effort: M

## A4. Purge scheduler + confirm UI
- Problem: `purge_resigned` manual-only, fail-open, no UI (COMPILED #3 S5/C2/C8/C12/P5).
- Proposal: weekly cron/Task Scheduler line + `--days` floor(≥30)+fail-closed txn; Offboarding tab gets dry-run preview + confirm button hitting `POST /api/purge/`.
- Value: flips S5 from PARTIAL/manual-only to COVERED/automatic.
- Effort: M

## A5. ExpenseClaim wiring (or delete)
- Problem: ExpenseClaim model exists, routes dead/empty stubs (Justif #11, COMPILED #12-edge).
- Proposal: `CRUD /api/expense-claims/` + approve/reject actions; claims section in dashboard bound to live fetch (else delete model+stubs).
- Value: flips S4-UX "claims toast-only" slice to live.
- Effort: S
