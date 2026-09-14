# FrappeHR (frappe/hrms) vs Kumon EMS — Feature Comparison

Sources: `frappe/hrms @ develop` — `hrms/hr/doctype` (~150 doctypes),
`hrms/payroll/doctype` (~40 doctypes), product pages at frappe.io/hr.
Kumon EMS side verified against `core/models.py`, `api/urls.py`,
`core/views.py` @ `125a29d`. FrappeHR is a decade-old, 8.8k-star,
enterprise HRMS; the comparison below is scoped to what a capstone can
realistically borrow, not to parity.

## FrappeHR's modules (what it has)

1. **Employee lifecycle** — onboarding with templates + task checklists
   (`employee_onboarding`, `employee_boarding_activity`), transfers
   (`employee_transfer`), promotions (`employee_promotion`), separations with
   templates (`employee_separation`), exit interviews (`exit_interview`),
   full-and-final settlement (`full_and_final_statement`), appointment letters
   (`appointment_letter`), employee skill maps, health insurance, vehicle logs.
2. **Leave & attendance** — leave types/policies/allocations/periods
   (`leave_type`, `leave_policy`, `leave_allocation`, `leave_period`),
   leave ledger (`leave_ledger_entry`), encashment, compensatory leaves,
   block lists, holiday lists; check-in/out with geolocation
   (`employee_checkin`), attendance requests, overtime slips, shift types,
   shift assignments/requests/schedules, staffing plans, auto-attendance.
3. **Payroll & taxation** — salary structures + assignments, salary slips,
   payroll entries/periods, additional salary, incentives, retention bonuses,
   benefits ledger, loans/advances hooks, gratuity rules, income-tax slabs
   with exemption declarations and proof submission.
4. **Expenses & travel** — expense claims with types, advances, taxes,
   costing; travel requests with itineraries; employee advances.
5. **Performance** — goals, KRAs, appraisal cycles/templates, 360° feedback
   (`employee_performance_feedback`), training programs/events/results.
6. **Recruitment** — requisitions, job openings, applicants, offers, interviews
   with feedback, onboarding handoff.
7. **Helpdesk/grievance** — `employee_grievance` with types (real workflow).
8. **Platform** — roles/permissions, push/mobile PWA notifications
   (`pwa_notification`), reports + Org chart, multi-company/currency,
   Docker/CI/semgrep, 11k commits of hardening.

## What Kumon EMS already matches

Employee/department CRUD, leave filing with approval, clock-in/out with
duplicate + open-record guards, shift rosters with overlap guard + conflict
endpoint, manual payroll runs with server-computed net_pay, soft-delete with
30-day purge, audit trail, session+token auth, notifications inbox, messages,
claim statuses, activity feed, guided tour. Roughly: FrappeHR's items
1 (partial), 2 (partial), 3 (manual subset), 7 (intake only).

## Gaps, ranked by value for this capstone

### Tier 1 — closes SOP verdicts / panel-visible holes
1. **Leave balances + allocations.** Today: leaves are just rows; no quota,
   no balance, no year reset. FrappeHR: `leave_allocation` + ledger.
   Improvement: `LeaveAllocation(employee, leave_type, days_total, period)` +
   balance computed on read; small model, big SOP2 win.
2. **Real grievance workflow.** Today: intake buttons are toast-only.
   FrappeHR: typed grievances with states. Improvement: status field +
   assign/resolve endpoints on the existing intake (half of S4's mock surface).
3. **ExpenseClaim wiring.** Today: model exists, zero routes (tagged UNDER
   DEVELOPMENT). FrappeHR: full advances/taxes/costing. Improvement: minimum
   is H3-style routes + approvals; advances/taxes stay out of scope.
4. **Holiday calendar.** Today: none — rosters/leaves ignore holidays.
   FrappeHR: holiday lists with one-click regional pull. Improvement: tiny
   `Holiday(date, name)` table + conflict endpoint includes it.

### Tier 2 — believable HR depth, small builds
5. **Payslips.** Today: numbers in a table. FrappeHR: salary slips per
   employee per period. Improvement: printable slip view over existing
   PayrollItems (read-only page, no new model).
6. **Overtime slips.** Today: clock times recorded, never used. FrappeHR:
   `overtime_slip`. Improvement: derive OT hours from attendance vs shift and
   store as a slip row feeding payroll deductions/additions.
7. **Onboarding checklists.** Today: account creation only. FrappeHR:
   templated boarding activities. Improvement: `OnboardingTask` list per new
   hire (documents, orientation, account setup) with checkboxes.
8. **Shift requests + swaps.** Today: admin assigns top-down. FrappeHR: swap
   requests. Improvement: employee-initiated swap request with manager
   approve (reuses leave-approval UX pattern).
9. **Attendance corrections.** Today: bad clock data is immutable.
   Improvement: correction request → approval → amends row (audited).

### Tier 3 — structural, borrow ideas not code
10. **Roles/permissions.** Today: all authed users see everything. FrappeHR:
    granular roles. Improvement: 3 Django groups (HR admin / manager /
    employee) gating sensitive endpoints first, UI later.
11. **Appraisal goals/KRAs.** Today: free-text reviews. Improvement: goal rows
    linked to reviews when performance UI goes live.
12. **Recruitment.** Today: nothing. FrappeHR: full pipeline. Improvement:
    out of scope — applicants KPI is demo; say so in the paper, don't build.

## How to improve (suggested order)

1. Wire what's built but dark (ExpenseClaim routes) before building anything
   new — dead code embarrasses faster than missing code.
2. Pick ONE Tier-1 item per remaining sprint (balances → grievance workflow →
   holidays); each is a single model + endpoints + tests, same TDD pattern
   as H1–H3.
3. Payslip print view + overtime derivation turn existing data into visible
   value with almost no new schema.
4. Roles/permissions before any demo with real people (today everyone sees
   salaries).
5. Say no to recruitment, tax slabs, multi-currency, mobile app — each is a
   thesis on its own; the paper should name them as future work, not stubs.
