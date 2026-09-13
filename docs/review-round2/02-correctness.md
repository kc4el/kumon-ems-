# Review round 2 — correctness & data integrity (new code only)

Scope: race conditions, atomicity gaps, guard edge cases, Decimal/timezone handling, purge, soft-delete/CASCADE, migration safety.

## HIGH
- Shift overlap guard is validate-only, no DB constraint — two concurrent overlapping creates both pass `exists()` then both save. No `transaction.atomic` on shift create/update. `core/serializers.py:85-99`
- Purge deletes local row even when Supabase delete fails (`except: log; emp.delete()` unconditional) → orphaned auth users; upstream-first ordering with no skip/abort is backwards. `core/management/commands/purge_resigned.py:29-33`
- Payroll PATCH without `base_pay` → `validated_data["base_pay"]` KeyError → 500. `_save_computed` assumes full payload on update path. `core/views.py:276,291-292`

## MEDIUM
- Employee create duplicate race returns 502, not 409: concurrent same-email POSTs both pass the `iexact exists()` check (`core/views.py:114`), loser hits DB `IntegrityError` inside the broad `except Exception` (`core/views.py:136`) → "upstream" 502. Same block: `record_id` (`:121`) is dead — save uses `created_user_id` (`:134`); a `create_user` response with `user=None` raises AttributeError with no rollback → orphan Supabase user.
- App-level email check is `iexact` but DB `unique=True` (`core/models.py:28`) is case-sensitive on SQLite/Postgres → `Jane@x` vs `jane@x` blocked by API yet allowed by DB (or vice versa depending on backend); defense layers disagree.
- Attendance update path unguarded: `validate()` skips when `self.instance` set (`core/serializers.py:44`) and `atomic`+409 exists only in `perform_create` (`core/views.py:165-170`) → PUT to a duplicate (employee,date) raises unhandled `IntegrityError` → 500. Same-condition status split: fast-path 400 (`api/tests.py:192-204`) vs race 409 (`:206-212`).
- Soft-delete re-DELETE overwrites `resigned_at=today` every call (`core/views.py:155-158`) → retention clock restarts, purge evadable. Bulk/queryset deletes bypass `perform_destroy` entirely → instant hard delete + CASCADE wipe.
- Purge `emp.delete()` cascades Attendance, LeaveRequest, PayrollItem, PerformanceReview (`core/models.py:43,57,88,99`) → 30-day purge destroys payroll history. Unaffected hard-delete paths still instant: PayrollRun detail (cascades its items), Attendance/Leave/Performance detail views use default `perform_destroy`.
- Clock-out locking is a no-op on this project's SQLite DB (`select_for_update`, `core/views.py:200-203`); `count()` then `.first()` re-queries, so the multi-open check can observe different snapshots. Phantom inserts aren't locked on any backend (no partial-unique on open rows).

## LOW
- Naive `clock_out` assumed UTC (`core/views.py:194-195`; `TIME_ZONE="UTC", USE_TZ=True`, `kumon_ems/settings.py:126-130`) → naive local-time input silently shifts the `clock_out < clock_in` comparison (`:217`); `==` (zero-duration) accepted; no check that `clock_out` date matches `Attendance.date` (cross-midnight silently OK).
- Overlap guard requires employee AND work_date AND both times (`core/serializers.py:85`) → rows with NULL `work_date`/`employee` (both nullable per migration 0006) skip validation entirely; `start >= end` reject (`:86-87`) also makes overnight shifts unrepresentable; `break_mins` unvalidated. Adjacent-boundary (`<`/`>`) and update self-exclusion (`:94-95`) verified correct.
- Purge boundary: `resigned_at__lte=cutoff` (`purge_resigned.py:23-24`) purges day-30 exactly; `--days` negative/zero unvalidated (negative purges everyone); per-employee, no transaction.
- Migration 0004 adds `unique_together (payroll_run, employee)` with no data migration — `migrate` on the existing `db.sqlite3` fails if duplicates already exist. 0005/0006 (nullable adds) are safe. Minor inconsistency: payroll race → 400 (`core/views.py:281-284`) vs attendance race → 409 (`core/exceptions.py:4`).

## Checked, no issue
- Payroll Decimal: DRF coerces `base_pay`/`deductions` to 2dp so `base - deductions` stays ≤2dp; `int 0` default subtracts cleanly. (Negative `net_pay` allowed — policy call, not a bug.)
- `MultipleObjectsReturned` on clock-out handled via explicit count → 409; shift adjacent-slot and different-employee cases covered by tests.
