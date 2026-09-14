# Round-3 feature overview (merged → chore/standard-format @ c5f7aae)
Suite: 100 tests (api/tests.py:83 + core/tests.py:17). Read-only review; no code changed.

## F1 — Leave allocations / balances / deficit notice (`feat/wt-leave`)
- What: per-employee-type-year entitlement + balance math + over-balance warning on approval.
- Endpoints: `GET/POST leave-allocations/`, `GET/PATCH/DELETE leave-allocations/<uuid>/`, `GET leave-balances/?employee=&year=`.
- Models: `LeaveAllocation` (unique employee/type/year); `LEAVE_DEFAULTS={Vacation:5, Sick:5}` fallback.
- Tests: `LeaveAllocationTests`(3) + `LeaveBalanceTests`(4) in api/tests.py; `LeaveDeficitTests` in core/tests.py:90.
- Deviations: balance computed in a Python loop (N+1), not an annotated queryset; type list falls back to Vacation/Sick with no allocation rows; deficit warning is text appended in the leave signal, not a separate kind.

## F2 — Request-based overtime slips (`feat/wt-ot`)
- What: overtime claimed against a completed attendance; hours auto-computed; approval notifies.
- Endpoints: `GET/POST overtime/`, `GET/PATCH/DELETE overtime/<uuid>/` (detail PATCH is status-only).
- Models: `OvertimeSlip` (employee, attendance, date, hours read-only, multiplier, status).
- Tests: `OvertimeSlipTests`(9) api/tests.py:1013; `OvertimeNotificationTests` core/tests.py:280.
- Deviations: hours = max(0, worked−8) server-side; multiplier still client-settable at create; notify via new pre/post_save signal pair, no audit row.

## F3 — Peer shift swaps (`feat/wt-swap`)
- What: requester/target roster swap with same-date + different-employee guards, atomic approval.
- Endpoints: `GET/POST shift-swaps/`, `GET/PATCH/DELETE shift-swaps/<uuid>/` (PATCH drives approve/reject).
- Models: `ShiftSwap` (requester_roster, target_roster, reason, status).
- Tests: `ShiftSwapTests`(7) api/tests.py:1115.
- Deviations: no separate approve endpoint — state machine lives in `ShiftSwapDetailView.patch`; approval re-runs the roster overlap guard per holder in one transaction; approve/reject notify but write no audit row.

## F4 — Attendance corrections (`feat/wt-corr`)
- What: propose clock-in/out fixes; approval applies them to the attendance row atomically.
- Endpoints: `GET/POST attendance-corrections/`, `GET/PATCH/DELETE attendance-corrections/<uuid>/`.
- Models: `AttendanceCorrection` (attendance, proposed_* nullable, reason, status).
- Tests: `AttendanceCorrectionTests`(6) api/tests.py:1300.
- Deviations: approve/reject via custom `patch()`, not a sub-action; audit + `kind="attendance"` notification inline in the view, not via signal; rejection notifies nobody.

## Migration map (linearized by c5f7aae)
| File | Model | Depends on |
|---|---|---|
| 0014_leaveallocation | LeaveAllocation | 0013_notification |
| 0015_overtimeslip | OvertimeSlip | 0014 |
| 0016_shiftswap | ShiftSwap | 0015 |
| 0017_attendancecorrection | AttendanceCorrection | 0016 |

## Worktree / merge notes
- 4 branches (`feat/wt-leave|ot|swap|corr`) each authored its own `0014_*` off 0013 → filename + dependency collision at merge.
- c5f7aae renamed 0014_overtimeslip→0015, 0014_shiftswap→0016, 0014_attendancecorrection→0017 and rewired deps (0015→0014, 0016→0015).
- TZ+localdate fix (rode in with f226e0a): `TIME_ZONE` UTC→Asia/Singapore; `now().date()`→`localdate()` in EmployeeDetailView (views.py:210,217) and purge_resigned cutoff.

## Consistency review (new code vs conventions)
- PASS explicit fields: all 4 new serializers list fields; pre-existing `__all__` (serializers.py:29,51,150,220,236,257) untouched.
- PASS `{error}` envelope: all custom Responses use it; `core/exception_handler.py:4` flattens every DRF error into `{error}` anyway.
- VIOLATION 409-rule: duplicate LeaveAllocation → 400. Serializer (serializers.py:124) keeps the auto UniqueTogetherValidator and views (views.py:391) catch no IntegrityError — cf. PayrollItem pattern (serializers.py:228, views.py:646).
- MINOR 409-rule: re-deciding a decided swap returns 400 (views.py:549) — well-formed but conflicting → 409 fits better.
- GAP audit-on-mutation: no `EmployeeAuditLog` for allocation CRUD, overtime create/approve (signals.py:201 notifies only), swap approve/reject (views.py:553,605 notify only). Correction approve is the only new path that audits (views.py:309).
- STYLE: function-level imports in `leave_balance()` (views.py:402,404); signals.py:167 import is cycle-avoidance, fine. black/isort not installed here — import order/line length checked by eye, clean.
- Route names OK: `leave-balances` (urls.py:96) is a singleton like `dashboard-summary`; `overtime/` singular matches `performance/`.

## Residual risks
1. `leave_balance()` loops approved leaves in Python (N+1), mixes float/int; fine at current scale.
2. Client sets `multiplier` at overtime create (not read-only) — approval trusts it; cap or server-side table wanted.
3. Detail PATCH on overtime/swap silently drops non-status fields — commented, still silent.
4. TZ flip changes the local-day boundary for `resigned_at`/purge/roster dates vs old UTC rows.
5. Three new mutation paths write no audit rows → activity-feed blind spots.
6. Next worktree feature must branch past 0017 or the 0014-collision repeats.
