# 04 Data Integrity — Round 4 (NEW only; round-3 items excluded)

Scope: core/models.py + migrations 0013–0017 + core/serializers.py + core/views.py. HEAD 4c6864c.

## HIGH
1. [HIGH] OvertimeSlip: no DB uniqueness — double POST creates 2 slips for one attendance; app has no pending/dup guard. Add UniqueConstraint(attendance) or (employee,attendance). — core/models.py:64-83
2. [HIGH] ShiftSwap pending guard is app-only `.exists()` (serializers.py:209-216); concurrent POSTs both pass → duplicate pendings, no IntegrityError/409. Needs partial-UniqueConstraint(status=Pending) or atomic guard. — core/serializers.py:209
3. [HIGH] ShiftRoster overlap guard is app-only `.exists()` (serializers.py:168-177); no DB exclusion constraint → concurrent overlapping inserts both succeed (SQLite select_for_update no-op also applies). — core/serializers.py:168
4. [HIGH] LeaveAllocationDetailView has no IntegrityError→409 on PUT/PATCH; duplicate edit → 500. Create path maps to 409 (views.py:395-402) but detail view has no perform_update. — core/views.py:405-407

## MEDIUM
5. [MED] ShiftSwap both FKs CASCADE (models.py:147-152): deleting one roster silently deletes swap history (both requester+target sides). Audit loss; consider PROTECT or SET_NULL. Orphan-by-delete is "ok" only if history loss accepted.
6. [MED] Attendance CASCADE fan-out: delete wipes OvertimeSlip + AttendanceCorrection rows silently (models.py:67,87). Same for Employee CASCADE → slips/corrections/allocations/notifications. No PROTECT/audit retention.
7. [MED] Swap reject path creates Notification with `employee=swap.requester_roster.employee` unchecked (views.py:569); null-employee roster → NOT NULL IntegrityError → 500. Approve path guards null (:594) but reject does not.
8. [MED] OvertimeSlip.date vs attendance.date never cross-checked (views.py:467-482 checks owner + completeness only) → slip date can disagree with attendance date; inconsistent rows persist.
9. [MED] AttendanceCorrection: unlimited Pending rows per attendance; no partial-unique (attendance where Pending). Spam/double-approve ambiguity. — core/models.py:85-100
10. [MED] LeaveAllocation.leave_type free text, no choices/normalization (models.py:120): "Vacation" vs "vacation" bypasses unique_together (employee,leave_type,year) → duplicate effective allocations + leave_balance fallback mismatch (views.py:418).
11. [MED] Notification.kind free text, no choices (models.py:246); views write "shift" (views.py:570,618) but nothing enforces set. Typo kinds fragment filtering.
12. [MED] unique_together (legacy) on LeaveAllocation (models.py:125), Attendance (:54), PayrollItem (:182) still works but deprecated; preferred UniqueConstraint with name for PG/SQLite parity + clearer errors.

## LOW
13. [LOW] PayrollItem.deductions default=0.00 float, not Decimal (models.py:178); mix with Decimal base_pay risks float artifact at model default. Use Decimal("0.00").
14. [LOW] OvertimeSlip.hours max_digits=5/dec-2 allows 999.99h; zero-hour slips persisted (clamped max(0,…), views.py:481) with no MinValueValidator. Noise rows.
15. [LOW] LeaveAllocation.days_total dec-1 (models.py:122) vs integer day-count math in leave_balance (views.py:429); half-day ok but quarter-day values silently stored, remaining float-cast (:430) hides precision.
16. [LOW] Migrations 0013–0017 are CreateModel-only, no alters/backfills — safe; no PG-vs-SQLite divergence introduced. Partial-unique one_open_attendance (0010) valid on both (PG partial index; SQLite ≥3.8 supports WHERE). No action.
