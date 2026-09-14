# IDEAS-B — Net-New Enhancements (beyond SOPs)

Scope: chore/standard-format @ cf89b71. Cap 8; none required to flip a verdict.

## B1. Payroll/attendance CSV export
- Problem: no export; panel must screenshot tables.
- Proposal: `GET /api/reports/payroll.csv?month=` streaming response; Export button on payroll + attendance tables.
- Value: one-click evidence for defense appendix.
- Effort: S / Depends-On: none.

## B2. Audit-log dashboard
- Problem: `EmployeeAuditLog` writable table, no viewer (COMPILED §3.4.4).
- Proposal: read-only `GET /api/audit-logs/` + filter by actor/date; Audit tab with table + actor filter.
- Value: makes "tamper-evident" claim demonstrable.
- Effort: S / Depends-On: none.

## B3. Role-scoped views (manager vs staff)
- Problem: single dashboard shows everything incl. purge/offboarding.
- Proposal: `UserProfile.role` + permission-gated endpoints; hide admin tabs client-side by role.
- Value: least-privilege story for S4-safety.
- Effort: M / Depends-On: B7 profiles.

## B4. Shift-swap request flow
- Problem: swaps handled verbally, no record.
- Proposal: `ShiftSwap(requester, shift, target, status)` + approve endpoint; Shifts tab "Request swap" dialog.
- Value: auditable swap trail without new SOP.
- Effort: M / Depends-On: A1 roster-block.

## B5. Attendance correction requests
- Problem: wrong clock times need admin DB edits.
- Proposal: `AttendanceCorrection(attendance, proposed, status)` + approve applies time; attendance row "Request fix" button.
- Value: closes clock-out edge residue cleanly.
- Effort: S / Depends-On: none.

## B6. Password reset (token-emailed)
- Problem: no reset path; token lifecycle already weak (COMPILED #2).
- Proposal: `POST /api/auth/password-reset/` issuing expiry-stamped token; login page "Forgot?" link.
- Value: completes auth lifecycle for S4.
- Effort: M / Depends-On: A2 notifications (mail channel).

## B7. Employee profiles + avatars
- Problem: directory is bare names/roles.
- Proposal: `UserProfile(bio, phone, avatar_url)` + `PATCH /api/me/`; profile drawer on directory click.
- Value: humanizes demo; anchor for B3 roles.
- Effort: S / Depends-On: none.

## B8. Dashboard cached summary
- Problem: 5× `count()` per summary load (Justif #10).
- Proposal: single aggregate query + 60s cache on `DashboardSummaryView`; skeleton loaders replace demo fallback.
- Value: faster load; kills demo-confusion path.
- Effort: S / Depends-On: none.
