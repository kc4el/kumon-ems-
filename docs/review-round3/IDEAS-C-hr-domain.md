# IDEAS-C — HR-Domain Functions (missing small-branch HRIS pieces)

Scope: chore/standard-format @ 81046d1. Cap 10; excludes A/B coverage (no roster-block, notifications, payroll-derive, purge, expenses, CSV, audit viewer, roles, swaps, corrections, reset, profiles, summary cache).

## C1. Payslip generation + employee view
- Problem: PayrollRun/Item totals exist but staff never see a payslip.
- Proposal: `GET /api/payslips/?month=` scoped to request.user; `GET /api/payslips/<id>/pdf/` renders existing item (gross/deductions/net).
- UI: "My Payslips" list + print-friendly slip view.
- Value: closes payroll loop for non-admin staff. / Effort: M / Depends-On: A3 derive.

## C2. Leave balances / quotas
- Problem: LeaveRequest has no quota, so unlimited leave is approvable.
- Proposal: `LeaveQuota(employee, year, sick_days, vacation_days)` + decrement on approve; `GET /api/leave-balances/` blocks over-quota requests server-side.
- UI: balance chips on leave form ("Vacation left: 7").
- Value: makes leave approval enforceable policy, not vibes. / Effort: S / Depends-On: none.

## C3. Overtime tracking
- Problem: extra hours outside ShiftRoster have no record and never reach payroll.
- Proposal: `OvertimeLog(employee, date, hours, reason, status)` + approve endpoint; approved hours feed `PayrollRun.derive()`.
- UI: overtime tab with request/approve buttons.
- Value: auditable OT pay instead of verbal claims. / Effort: M / Depends-On: A3 derive.

## C4. Employee documents / 201 files
- Problem: contracts, IDs, certificates live in paper folders, not the portal.
- Proposal: `EmployeeDocument(employee, kind, file, uploaded_by)` + `CRUD /api/documents/` with role-scoped read; file upload via DRF parsers.
- UI: documents section on employee detail with kind filter.
- Value: single source of truth for staff records. / Effort: M / Depends-On: B3 roles (for scoping).

## C5. Onboarding checklist
- Problem: new-hire setup (account, contract, orientation) is ad hoc and untracked.
- Proposal: `OnboardingTask(employee, title, done, done_by)` seeded from template on Employee create; `PATCH /api/onboarding/<id>/` toggles completion.
- UI: checklist widget on employee detail with progress bar.
- Value: no forgotten setup steps for new branch staff. / Effort: S / Depends-On: none.

## C6. Offboarding clearance
- Problem: `purge_resigned` deletes leavers with no clearance trail (assets, accounts, final pay).
- Proposal: `OffboardingClearance(employee, item, signed_by, signed_at)`; purge blocked until all items signed.
- UI: clearance tab with per-item sign-off + purge gate warning.
- Value: prevents premature purge and missing handovers. / Effort: M / Depends-On: A4 purge scheduler.

## C7. Org chart
- Problem: Department/Employee exist but reporting lines are invisible.
- Proposal: `Employee.reports_to` self-FK + `GET /api/org-chart/` nested tree; read-only recursive serializer.
- UI: simple tree view grouped by department.
- Value: visible structure for a small branch at near-zero cost. / Effort: S / Depends-On: none.

## C8. Holiday calendar
- Problem: leave approvals ignore public holidays, inflating deductions.
- Proposal: `Holiday(date, name)` + `CRUD /api/holidays/`; leave-day count and roster exclude holiday dates.
- UI: mini calendar highlighting holidays + leave overlap warning.
- Value: correct leave accounting and scheduling. / Effort: S / Depends-On: C2 quotas.

## C9. Salary structure / grades
- Problem: pay rates are per-employee free text, so inequities hide.
- Proposal: `SalaryGrade(code, title, base_pay, allowances)` + `Employee.grade` FK; payroll derive uses grade base unless overridden.
- UI: grade table + grade picker on employee form.
- Value: consistent, explainable pay bands. / Effort: M / Depends-On: A3 derive.

## C10. Service awards / tenure milestones
- Problem: long-serving branch staff get no system recognition.
- Proposal: anniversary computed from `Employee.hire_date`; `GET /api/milestones/?month=` lists upcoming 1/3/5-yr marks.
- UI: dashboard widget + optional notification hook.
- Value: cheap retention signal fitting a Kumon branch. / Effort: S / Depends-On: A2 notifications (optional).
