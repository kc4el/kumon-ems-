# Round 5 — 04 · Leave, Overtime, Swaps, Corrections

Scope: `LeaveAllocation`/balances, `OvertimeSlip` + signal accrual, `ShiftSwap`
two-sided flow, `AttendanceCorrection` approval, leave-state transitions.
Branch `chore/standard-format`. No dev servers started; verification via area
tests (`DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test …`) plus
throwaway API probes (deleted after the run, not committed).

```
DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test \
  api.tests.LeaveAllocationTests api.tests.LeaveBalanceTests \
  api.tests.OvertimeSlipTests api.tests.ShiftSwapTests \
  api.tests.AttendanceCorrectionTests \
  core.tests.LeaveDeficitTests core.tests.OvertimeNotificationTests \
  core.tests.NewFeatureAuditTests
# Ran 38 tests … OK
```

## Verified working (evidence)

- **LeaveAllocation CRUD + duplicate guard.** POST 201; second identical
  POST → 409 `{"error"}` (`core/views.py:416-427`); anon list → 403.
  Create writes one audit row (`core/signals.py:217-223`).
  Tests: `api/tests.py:986-1023`, `core/tests.py:329-341`.
- **Leave balances.** `leave_balance` (`core/views.py:435-455`) clips
  approved ranges to the queried year; `LeaveBalanceView`
  (`core/views.py:458-485`) falls back to `LEAVE_DEFAULTS` Vacation/Sick 5
  (`core/models.py:114`) when no allocation exists; missing/bad params → 400.
  Over-balance approval is *allowed by design* and yields negative `remaining`
  (`api/tests.py:1077-1099`). Tests: `api/tests.py:1026-1099`.
- **Leave deficit notice.** Approving into negative emits exactly one
  `kind="leave"` “…over balance” notification; within-balance approval emits
  none (`core/signals.py:164-181`). Tests: `core/tests.py:91-134`.
- **Overtime accrual is server-computed.** `hours = max(0, round(worked-8, 2))`
  (`core/views.py:505-507`); posted `hours` ignored (read-only,
  `core/serializers.py:134-147`); custom `multiplier` accepted; incomplete /
  other-employee / missing attendance → 400 `{"error"}`; approve PATCH → 200.
  Tests: `api/tests.py:1162-1229`.
- **Overtime signal accrual.** Approve fires one `kind="payroll"`
  “Overtime approved: …” notification + audit rows for request and approval
  (`core/signals.py:204-237`); re-saving an already-Approved slip notifies
  once, not twice (guard `core/signals.py:208`; probe: two PATCH Approves →
  1 payroll notification). Tests: `core/tests.py:281-326,343-371`.
- **ShiftSwap request guards.** Same-employee → 400, different dates → 400
  (`core/serializers.py:194-217`), second pending swap on either roster → 409.
  Tests: `api/tests.py:1260-1330`.
- **ShiftSwap approve (atomic two-holder swap).** PATCH Approved swaps both
  roster holders in one transaction, notifies *both* employees, writes audit
  (`core/views.py:610-649`); overlapping third assignment → 409 with full
  rollback, rows unchanged, swap stays Pending; identical-slot pair swap
  succeeds (pair excluded from own clash check). Reject keeps rows + notifies
  requester; re-deciding a closed swap via PATCH → 409
  (`core/views.py:582-586`). Tests: `api/tests.py:1332-1485`.
- **AttendanceCorrection approve.** Create 201 leaves the row untouched; empty
  proposal / inverted times → 400 (`core/serializers.py:80-105`); approve
  PATCH applies proposed times atomically + status-only (extra payload keys
  such as `reason` ignored) + audit + `kind="attendance"` notification;
  reject changes nothing and writes no “corrected” audit
  (`core/views.py:294-346`). Double-approve PATCH is idempotent (200, row
  applied once — probe). Tests: `api/tests.py:1488-1604`.

## Bugs found (repro)

All reproduced via authenticated `APIClient` against a test DB (scratch
module, removed afterwards). `A`/`B` = two employees, same-day rosters
09–13 / 14–18 unless noted.

1. **Leave accepts arbitrary status strings.** PATCH `/api/leaves/<id>/`
   `{"status": "Bogus!!!"}` → 200, persisted; GET returns `"Bogus!!!"`.
   Cause: `LeaveRequest.status` has no `choices` (`core/models.py:103-111`)
   and `LeaveRequestSerializer` has no `validate`
   (`core/serializers.py:108-121`); detail view is a plain generic
   (`core/views.py:411-413`). Dashboard counts use `__iexact`, so bogus rows
   are silently invisible there (`core/views.py:79-84`).
2. **Leave accepts `end_date < start_date`.** POST with start 2026-05-10 /
   end 2026-05-01 → 201. Same missing-validation cause as (1). An approved
   inverted range contributes negative `used` in `leave_balance`
   (`core/views.py:444-454`), inflating `remaining`.
3. **ShiftSwap PUT bypasses the decide guard.** Reject via PATCH (200), then
   `PUT /api/shift-swaps/<id>/` with `status: Approved` → 200,
   `status == "Approved"` — but holders are **not** swapped and **no**
   notifications are sent. Cause: the 409 + `_approve_swap` live only in
   `patch()` (`core/views.py:577-608`); `perform_update`
   (`core/views.py:567-575`) saves any status with no side effects, and PUT
   never routes through `patch()`.
4. **Correction Approved → Rejected does not revert the row.** After approve
   (row 08:30/17:30), PATCH Rejected → 200, `status == "Rejected"`, but the
   attendance row keeps the corrected times. Cause: the Rejected branch
   (`core/views.py:310-314`) flips status without restoring prior times.
5. **Correction PUT (and status-less PATCH) bypasses application.**
   `PUT /api/attendance-corrections/<id>/` with `status: Approved` → 200,
   `status == "Approved"`, but the attendance row is never updated. Cause:
   side effects exist only in `patch()` when `"status"` is present
   (`core/views.py:298-346`); generic update path saves status only.
6. **Duplicate overtime slips per attendance.** Two POSTs for the same
   attendance → 201 + 201 (`count == 2`). No unique constraint on
   `OvertimeSlip.attendance` (`core/models.py:64-82`); each slip is
   independently approvable, each approval emitting a payroll notification.
7. **Deleting an Approved leave silently restores balance.** DELETE → 204;
   `used` drops 2 → 0 with no audit row and no guard (generic destroy,
   `core/views.py:411-413`; no delete signal in `core/signals.py`).
8. **Negative allocation accepted.** POST `days_total: "-3.0"` → 201. No
   `MinValueValidator` on `LeaveAllocation.days_total`
   (`core/models.py:117-126`), unlike `ExpenseClaim.amount`
   (`core/models.py:197-201`).

## State-machine holes

- **Leave: no transition machine at all.** Any → any via PATCH
  (Approved → Pending regress probed → 200; Rejected → Approved re-approval
  allowed, re-counting `used`). No terminal states, no balance enforcement
  (over-approval intentional, deficit-noted), no double-approval dedup needed
  — re-PATCH Approved adds no extra notification (signal guard
  `core/signals.py:166-167`) — but *creation itself* emits a “Leave Pending”
  notification, so every submission notifies, not just decisions.
- **Overtime: value-checked, transition-open.** Bogus status → 400 (model
  choices, `core/models.py:73-81`), but Approved → Pending regress → 200
  re-opens the slip and a later re-approval emits a *second* payroll
  notification (each Pending → Approved edge notifies; only exact double-save
  is deduped, `core/signals.py:206-209`). No `Rejected → …` or terminal-state
  rules; `perform_update` (`core/views.py:514-517`) ignores everything but
  status (good) yet enforces nothing about it.
- **Swap: one-sided approval.** The “two-sided” element is only the
  requester/target roster pair; approval is a single unilateral PATCH by any
  authenticated user — there is no counterparty (target employee) consent
  step, no expiry/cancel-by-requester path, and (per bug 3) the PUT path
  breaks the Pending → decided invariant entirely (Approved status with no
  swap). PATCH-side regress (Approved → Pending) is correctly 409.
- **Correction: asymmetric guards.** Approve is idempotent-safe and
  race-safe (`select_for_update`, `core/views.py:315-320`); reject is a blind
  status flip with no row revert (bug 4) and no audit; Rejected → Approved
  re-applies (fine); multiple Pending corrections on one attendance are
  allowed with last-approve-wins and no conflict warning; DELETE of a
  correction (any status) is permitted with no guard.
- **Cross-cutting.** All four flows rely on view-level checks with no
  model-level transition enforcement, so ORM writes, admin edits, and the
  generic PUT/PATCH fall-throughs bypass every rule. Cheapest structural fix
  covering bugs 1–5, 8 and most holes: `choices=` + `validate()`/transition
  map on the serializers, route all status writes through the guarded
  `patch()` handlers (or `perform_update`), and add the missing validators
  (non-negative allocation, `start ≤ end`, one pending correction / one slip
  per attendance).
