# Round 6 — Leave / Swap / OT / Correction logic (post T5–T7)

Scope: `core/views.py`, `core/serializers.py`, `core/signals.py`, `core/models.py`
after `8a1ea4f` (leave validation), `ffe3b79` (swap PUT guard), `75e6acd`
(single OT slip). Full suite: 133 tests pass except 2 pre-existing TZ
artifacts (see L8). 16 boundary probes run transiently (file removed after);
13 fail (= bugs below), 2 pass (= verified OK), 1 errored then confirmed on
retry. Frontend (`static/js/dashboard.js`, `pages/dashboard.html`) sends no
leave/swap/OT/correction status writes — all findings are backend.

## High

### H1 — PUT on attendance-correction bypasses the decision guard
`core/views.py:351-404` — `AttendanceCorrectionDetailView` defines `patch()`
with approve/reject logic but no `put()` override, so PUT takes the generic
update path. This is the exact bug class `ffe3b79` fixed for swaps, missed here.
Repro: create correction (proposed 08:00), then
`PUT /api/attendance-corrections/<id>/ {attendance, reason, status:"Approved"}` →
200, correction reads `Approved`, but attendance `clock_in` stays 09:00 and no
audit row / notification is created. Probe P2 confirmed. Same path also lets
PUT demote `Approved→Pending` and edit proposals on decided corrections.

### H2 — Rejecting a swap with an unassigned requester roster → HTTP 500
`core/views.py:665-677` — reject path does
`Notification.objects.create(employee=swap.requester_roster.employee, …)`, but
`ShiftRoster.employee` is nullable (`core/models.py:150-152`) and
`Notification.employee` is NOT NULL (`core/models.py:262`). The create
serializer only blocks both-None (`core/serializers.py:216-219`, None==None),
so a swap pairing an unassigned roster with an assigned one is accepted.
Repro: POST swap `{requester_roster: <unassigned>, target_roster: <assigned>}`
→ 201; `PATCH {status:"Rejected"}` → unhandled `IntegrityError:
NOT NULL constraint failed: core_notification.employee_id` → 500 (probe P10,
traceback confirmed). The approve path guards unassigned rosters with 400
(`views.py:694-695`); reject has no equivalent.

### H3 — Approve-then-reject keeps the corrected times; no revert (known, confirmed)
`core/views.py:368-372`; model `core/models.py:93-108` stores no prior values.
Repro: approve correction (clock_in 09:00→08:00), then reject → 200,
`status=Rejected` but attendance keeps 08:00 (probe P8b). There is no
revert path at all, and M5 below makes the bad state reachable in both orders.

## Medium

### M1 — `leave_balance` double-counts overlapping approved leaves
`core/views.py:504-514` sums `(end-start).days+1` per row with no overlap
dedup. Repro: allocation 10.0; approved 05-01→05-03 and 05-03→05-05 →
`used=6`, correct unique-day count is 5 (probe P1).

### M2 — Overlapping leaves are never rejected
`core/serializers.py:108-134` checks only `end < start`. Repro: approved
05-01→05-03 exists; POST overlapping 05-02→05-04 → 201 (probe P4, expect 409).
Root cause shared with M1; either overlap rejection or dedup counting is needed.

### M3 — Swap approval never revalidates parties/date (TOCTOU)
`core/views.py:662-663,685-724` — `_approve_swap` trusts the rosters as they
are at decision time. Repro: request swap A↔B, then
`PATCH /api/shift-rosters/<rb>/ {employee: C}`, then approve → 200, holders
become C↔A although C never consented and the request named A↔B (probe P9).
Same gap if roster dates are edited apart after request (same-date invariant
`serializers.py:220-221` is checked at request time only).

### M4 — Concurrent double-approve can swap holders twice
`core/views.py:686-693` locks both rosters (`select_for_update`) but never the
`ShiftSwap` row, and the `Pending` check at `:657` runs before the lock.
Two concurrent approves both pass the check → holders swapped A→B→A (net
no-op) with `Approved` status and 4 "swap approved" notifications. Code-level;
not probed under concurrency.

### M5 — Corrections are re-decidable; swaps are final (inconsistent)
`core/views.py:366-372` allows `Rejected→Approved` (probe P8 → 200) and
`Approved→Rejected` with no revert (H3), while swaps return 409 on any
re-decide (`:657-661`, covered by existing tests). One of the two finality
models must win.

### M6 — Exact-match status callers miss legacy lowercase rows; dashboard counts them
`core/views.py:508` (`leave_balance`), `:599` (`ShiftConflictView`),
`core/signals.py:169,206` (leave/OT notify), `core/serializers.py:222`
(swap pending guard) all compare exact `"Approved"`/`"Pending"`, while the
dashboard uses `status__iexact` (`views.py:89-94`). ORM-level saves bypass
serializer validation, so lowercase rows are representable. Repro: ORM-create
`status="approved"` leave 05-01→05-02 + roster same day → dashboard
`approved_leaves=1`, but balance `used=0` and conflicts `[]` (probe P14).
Consequence range: silent under-billing of balances, missed roster conflicts,
missed over-balance notices, duplicate "pending" swaps.

### M7 — Attendance create/update has no time-ordering or date-consistency guard
`core/serializers.py:48-63` checks duplicates only. Repro: POST attendance with
`clock_out` 8h before `clock_in` → 201 (probe P5); `date=09-10` with clocks on
09-11 → 201 (probe P5b). Only `AttendanceClockOutView` checks ordering
(`views.py:446-450`). Downstream: OT hours derive from the same unchecked
clocks (`views.py:565-566`).

### M8 — Balance view hides leave types without an allocation; `leave_type` unnormalized
`core/views.py:534-538` builds keys from allocations (fallback Vacation/Sick).
Repro: approved `Annual` leave, no allocation → keys `[Sick, Vacation]`, usage
invisible (probe P3). `LeaveRequest.leave_type` is free text (`models.py:114`),
so `"Vacation "` (trailing space) also misses its allocation → `used=0`
(probe P3b). Fix is normalize-on-write (strip; case rule) plus union of
requested types into the balance keys.

## Low

### L1 — OT multiplier unvalidated
`core/serializers.py:147-160` — `multiplier` accepts anything decimal-shaped.
Repro: `-2.00` → 201 (probe P6); `0` and `999.00` likewise. Sibling fields
(`LeaveAllocation.days_total`, `ExpenseClaim.amount`) both carry
`MinValueValidator`; this one has none. Related: 8h threshold hardcoded
(`views.py:566`), no cap — a forgotten clock-out (e.g. 72h) mints ~64h OT.

### L2 — OT demote→re-approve duplicates the approval notification
`core/signals.py:204-214` dedupes only consecutive `Approved` saves.
Repro: approve → demote to Pending → approve → 2 `kind=payroll` "Overtime
approved" rows (probe P12). `perform_update` (`views.py:579-582`) permits any
transition, so each re-approval notifies again.

### L3 — Filing a leave notifies the filer their own request is "Pending"
`core/signals.py:164-181` notifies on `created` regardless of status. Repro:
POST leave (no status) → `Leave Pending: 2026-05-01–2026-05-02` addressed to
the requester (probe P11). Self-notification noise; approval then adds a second
row for one lifecycle.

### L4 — Decided corrections accept proposal edits
`core/views.py:356-358` routes any PATCH without a `status` key to the generic
update. Repro: approve correction, then PATCH `{proposed_clock_in: 06:00}` →
200, proposal now disagrees with applied attendance (probe P16).

### L5 — Each swap approval writes 2 extra "Shift roster updated" audit rows
`core/signals.py:112-123` logs every roster save; `_approve_swap`
(`views.py:700-701`) saves both rosters. One approval = 1 swap-approved audit
+ 2 roster-updated audits attributed to the new holders (seen in probe logs).
Noise, not corruption.

### L6 — Cross-year over-balance notice checks the start year only
`core/signals.py:170-176` calls `leave_balance(…, start_date.year)`. A leave
spanning Dec→Jan can go negative in the end year with no deficit notice.

### L7 — No partial-day support despite `Decimal(0.1)` allocations
`LeaveAllocation.days_total` allows tenths (`models.py:138-140`) but `used` is
always whole days (`views.py:514`) and requests have no half-day form — `0.5`
allocations are unspendable. `float()` casts (`views.py:503,515`) also do day
arithmetic in binary float.

### L8 — Ancillary: 2 pre-existing failures are TZ artifacts (out of scope)
`api.tests.ApiTests.test_employee_delete_is_soft_delete` and
`..._is_idempotent`: `timezone.localdate()` (TZ=UTC → 09-12) vs
`date.today()` (host UTC+8 → 09-13). Fails only when run near midnight UTC;
unrelated to this scope, noted for triage.

## Verified OK (probed, no bug)
- Free-text/lowercase `status` on OT and swap PATCH → 400 (probe P15).
- Leave free-text status → 400 (existing `LeaveValidatorTests`).
- Swap PUT routed through decision guard (existing `test_put_after_reject_…`).
- One OT slip per attendance; correction approve applies times + audit + notif
  and ignores smuggled fields (existing tests).
- Cross-year clamp math inside `leave_balance` for the queried year.
