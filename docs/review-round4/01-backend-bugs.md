# 01 Backend logic bugs (round 4 — NEW only; round-3 items excluded)

## Views
1. [MED] `core/views.py:442-448` + `427-428` — LeaveBalance year unbounded: `int(year)` accepts 0/negative/100000; `date(year,1,1)` then raises ValueError → unhandled 500. No 1–9999 range guard, no try around `leave_balance`.
2. [MED] `core/views.py:787` — purge `dry = bool(request.data.get("dry_run", True))`: `bool("false")==True`, so explicit `"false"/0` still dry-runs (or misfires); no strict bool parsing. Plus `781-789`: negative `days` raises CommandError inside `call_command` → uncaught 500, not 400 (`purge_resigned.py:25` guard exists but view never checks).
3. [MED] `core/views.py:489-492` — OvertimeSlip PUT/PATCH silently drops everything but `status`: hours/date/attendance/employee edits validate then vanish, 200 returned. Status can also regress Approved→Pending with no guard.
4. [HIGH] `core/views.py:552-563` + `586-615` — ShiftSwap double-approve race: Pending check happens outside the transaction; `_approve_swap` locks both rosters but never re-locks/re-checks the swap row. Two concurrent approves both swap employees (net: swapped twice = original) while both write Approved + duplicate notifications.
5. [MED] `core/views.py:290-321` — correction approve ignores resigned employee: no `is_active`/`resigned_at` check before mutating attendance + writing audit/notification. Also `296-298`: `Attendance.get` unguarded → deleted attendance = unhandled 500 (no DoesNotExist catch).
6. [HIGH] `core/views.py:273-321` — approve logic lives only in `patch()`; full-update PUT on a correction flips `status` via default `perform_update` without applying proposed times or writing audit/notification — silent approve-without-apply (and Reject-without-record).
7. [LOW] `core/views.py:208-211` vs `213-237` — dead duplicate: `perform_destroy` soft-delete never runs (`destroy()` overridden); two copies of the same logic to drift.
8. [MED] `core/views.py:423` + `504-510` vs `79-84` — status case mismatch: balance `used` and ShiftConflict match exact `"Approved"` while dashboard counts `iexact`; a lowercase-status leave counts in the dashboard but never deducts from balance nor conflicts.

## Serializers (no domain guards)
9. [MED] `core/serializers.py:108-121` — LeaveRequest: no end<start check, free-text `status`/`leave_type` (anything writable, incl. auto-approve by POSTing status=Approved).
10. [MED] `core/serializers.py:124-131` — LeaveAllocation: `year`/`days_total` unbounded (negative days, year 0/99999 accepted; DB unique only).
11. [LOW] `core/serializers.py:134-147` + `220-224` + `236-239` — Overtime `multiplier` unbounded/negative; PayrollRun `__all__` with no end≥start check; PerformanceReview `score` unbounded int.

## Signals (double-fires)
12. [MED] `core/signals.py:112-123` — roster audit fires on EVERY update with no state check: each swap approve emits 2 spurious "Shift roster updated" rows on top of the swap audit (`250-261`) + 2 view notifications — ~3 audit rows per approve.
13. [MED] `core/signals.py:84-92` + `views.py:304-315` — correction approve that fills a null `clock_out` fires "Clocked OUT" audit from the Attendance post_save plus the explicit "attendance corrected" audit — double row per approve. `164-181`: notification also fires on leave *submission* (Pending), noise by default.

## N+1 / perf
14. [MED] `core/views.py:241,265,382,392,464,534,539,638` — all list querysets bare `.all()` with FK-heavy serializers (ShiftSwap has 2 roster FKs, PayrollItem 2 FKs); zero `select_related`/`prefetch_related` → N+1 per row. `433-460`: LeaveBalanceView runs alloc+leave queries per leave type in a loop.

## Timezone / date integrity
15. [MED] `core/serializers.py:48-63` — `Attendance.date` client-supplied, never checked against `clock_in.date()`: cross-midnight or lying `date` defeats the (employee,date) unique guard and corrupts daily counts. Same gap: OvertimeSlip `date` vs attendance date unchecked (`views.py:467-482`); `clock_out` `make_aware` without explicit tz (`341`) relies on default.
