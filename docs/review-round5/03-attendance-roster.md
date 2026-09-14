# 03 — Attendance & Roster (round 5 @ chore/standard-format)

Scope: clock-in/out guards, one-record-per-day rule, partial-unique open
attendance, overlap 409s, shift roster assign, attendance views
(daily/shift/leave tabs). Double-clock and overlap races.

## Verified working (with test evidence)

All runs: `DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test <labels>`
(full `api core`: 111 tests, all OK).

1. **One-record-per-day** — `unique_together = ("employee", "date")`
   (`core/models.py:53-54`) + serializer fast-path 409
   (`core/serializers.py:57-63`) + `IntegrityError` → 409 fallback in the
   view (`core/views.py:269-274`, routes `api/urls.py:60-68`). Second
   clock-in on the same day → 409 `{"error": ...}` whether the first row is
   open or already closed. Evidence:
   `api/tests.py:276-289`
   (`test_attendance_duplicate_returns_409_fast_path`) — PASS.
2. **Partial-unique open attendance** — `one_open_attendance_per_employee`
   (`clock_out IS NULL`, `core/models.py:55-60`, migration `0010`) means one
   employee can hold at most one unclosed row across all dates. A second open
   row (even on a different date) raises `IntegrityError`. Evidence:
   `api/tests.py:308-322` (`test_two_open_attendances_rejected_by_database`)
   and `api/tests.py:348-362` (`test_clock_out_second_open_rejected_by_database`)
   — PASS.
3. **Clock-out guards** — `POST /api/attendance/clock-out/`
   (`api/urls.py:79-83`, `core/views.py:349-403`): missing `employee_id` →
   400 (`:350-356`); malformed `clock_out` → 400 (`:357-366`); `clock_out`
   before `clock_in` → 400 (`:388-392`); no open row → 404 (`:377-381`); row
   locked with `select_for_update` (`:370-375`). Evidence:
   `api/tests.py:344-346`, `:364-380`, `:382-396` — PASS.
4. **Shift overlap 409s** — `ShiftRosterSerializer.validate`
   (`core/serializers.py:155-178`): `start_time >= end_time` → 400;
   overlapping `[start, end)` for the same employee + `work_date` →
   `Conflict409` (self excluded on update, `:174-175`). Adjacent slots and
   same slot for a different employee are allowed. Evidence:
   `api/tests.py:570-593` (overlap → 409), `:595-619` (adjacent → 201),
   `:621-648` (different employee → 201), `:650-668` (inverted → 400) —
   PASS.
5. **Roster assign persists via API** — `POST /api/shift-rosters/` → 201
   (`api/urls.py:104-109`, `core/views.py:548-550`), list ordered by
   `(work_date, start_time)` (`core/views.py:549`,
   `core/tests.py:151-154`); creation fires a `kind="shift"` notification
   (`core/signals.py:notify_shift_assignment`) and an audit row
   (`core/signals.py:log_shift_roster_action`).
6. **Leave-clash badges** — `GET /api/shift-rosters/conflicts/?employee=&date=`
   (`api/urls.py:110-114`, `core/views.py:520-545`) returns named
   `{roster, leave}` pairs; the shift tab renders one badge per live row via
   `refreshShiftConflictBadges` (`static/js/dashboard.js:1635-1660`).
   Evidence: `api/tests.py:876-904` — PASS (missing params → 400, `:906-911`).
7. **Attendance views (daily/shift/leave tabs)** — daily tab
   (`pages/dashboard.html:1284`) is a read-only live table over
   `GET /api/attendance/?page_size=50` with `● Clocked in` / `Complete`
   badges (`static/js/dashboard.js:1568-1599`); shift tab
   (`pages/dashboard.html:1457`) is a live roster table over
   `GET /api/shift-rosters/` (`static/js/dashboard.js:1601-1633`); leave tab
   (`pages/dashboard.html:1931`) files real requests via
   `POST /api/leaves/` (`static/js/dashboard.js:994-1010`). All three fall
   back to labelled demo data with a toast when the API is unreachable.
8. **Clock in/out audit trail** — `log_attendance_action`
   (`core/signals.py:cache_attendance_state`, `log_attendance_action`)
   writes "Clocked IN/OUT" rows once each. Evidence:
   `core/tests.py:39-61` — PASS.
9. **Correction workflow** — create → 201 leaving the row untouched; approve
   applies times (other payload fields ignored), writes audit +
   `kind="attendance"` notification; reject is a no-op; empty/inverted
   proposals → 400 (`core/views.py:294-346`,
   `core/serializers.py:80-105`). Evidence:
   `api/tests.py:1513-1560` — PASS.

## Bugs found (with repro)

**B1 — Direct `PATCH /api/attendance/<id>/` skips the time-order guard
(API-only, low-medium).** `AttendanceSerializer.validate` only checks
duplicates on create (`if not self.instance`,
`core/serializers.py:57-58`); there is no `clock_out > clock_in` check on
update, and `AttendanceDetailView.perform_update`
(`core/views.py:281-286`) maps failures to a generic 409. The
`clock_out < clock_in` → 400 guard exists only in `AttendanceClockOutView`
(`core/views.py:388-392`). Repro: create attendance with `clock_in = T`,
then `PATCH /api/attendance/<id>/ {"clock_out": T-1h}` → 200 with an
inverted shift. No test covers this path. Fix: validate time order in the
serializer for both create and update (the correction serializer already
does, `core/serializers.py:101-104`).

**B2 — Clock-in with null `clock_in` is accepted (API-only, low).**
`clock_in` is `null=True, blank=True` (`core/models.py:49`) with no
required validation, so `POST /api/attendance/ {"employee", "date"}` → 201
with `clock_in: null`. The row still occupies the partial-unique open slot
and blocks the real clock-in with a 409. Repro as stated. Fix: require
`clock_in` on create (default to now if absent, matching the clock-out
view's behaviour at `core/views.py:367-368`).

**B3 — Shift "Assign / Remove" board is DOM-only demo, disconnected from
the API (UI, medium).** `confirmAddStaff` (`static/js/dashboard.js:735-784`)
and `removeShiftStaff` (`:786-811`) only mutate the DOM, set the badge to
`'Draft'`, and never call `POST/DELETE /api/shift-rosters/` — no other
`apiFetch` targets that endpoint for writes (only the `GET` at `:1605`).
Repro: on the shift tab (`pages/dashboard.html:1780-1929`) assign staff →
`GET /api/shift-rosters/` unchanged → reload → assignment gone. Roster
overlap guards, clash badges, shift notifications and audit rows never fire
for these assignments. Fix or label: wire Assign to `POST
/api/shift-rosters/` (surfacing 409 overlaps) or mark the board demo.

**B4 — No clock-in/out affordance in the UI (UI, low).** The daily tab has
no punch buttons (`static/js/dashboard.js:1568-1599` only `GET`s); neither
`POST /api/attendance/` nor `POST /api/attendance/clock-out/` is called
from any UI code. Clock-in/out is API-only today.

## Race/edge cases

- **R1 — Roster overlap is check-then-insert with no DB backstop.**
  `ShiftRosterListCreateView` is a plain generic (`core/views.py:548-550`,
  no `perform_create`, no `IntegrityError` mapping) and `ShiftRoster` has
  no exclusion/unique constraint (`core/models.py:129-142`). Two concurrent
  overlapping `POST`s can both pass `clash.exists()` and both insert → 201
  + 201 double-booking. Attendance does not share this flaw (two DB
  constraints, §1-2). No concurrent-roster test exists. Fix: exclusion
  constraint on `(employee, work_date, tstzrange)` or
  `select_for_update` + re-check inside `perform_create`.
- **R2 — Double-clock race is safe.** Fast-path 409 plus
  `unique_together`/`one_open_attendance_per_employee` both raise
  `IntegrityError` → 409 under concurrency (`core/views.py:269-286`).
  Evidence: `api/tests.py:300-306` (`test_attendance_race_maps_to_409`) —
  PASS. Caveat: the race is simulated by mocking `transaction.atomic`;
  true concurrent Postgres behaviour is not exercised (test DB is sqlite).
- **R3 — Swap-approve re-checks overlap under row locks.**
  `ShiftSwapDetailView._approve_swap` (`core/views.py:610-649`) locks both
  rosters, swaps holders, re-runs the overlap guard, and rolls everything
  back on `Conflict409`. Evidence: `api/tests.py:1361-1386` (clash →
  409, rows and swap untouched) and `:1388-1415` (identical-slot pair swap
  succeeds — the two swapped rows don't clash with each other) — PASS.
- **R4 — "Multiple open clock-ins" 409 is defensive-only.**
  `core/views.py:382-386` handles `count > 1`, unreachable while the
  partial-unique constraint holds — it only fires for legacy rows predating
  migration `0010`. Keep, but don't rely on it.
- **R5 — Clash badges only flag `Approved` leaves (exact case).**
  `ShiftConflictView` filters `status="Approved"`
  (`core/views.py:530-535`, case-sensitive, unlike the `iexact` filters
  elsewhere): `Pending` (or lowercase `approved`) leaves never badge. Fine
  if intentional, but the UI copy ("already has an approved leave",
  `static/js/dashboard.js:349`) should say so — it does.
- **R6 — Double clock-out → 404, not 409.** First `POST clock-out` closes
  the row (200); a repeat finds no open row → 404 `{"error": "No open
  clock-in found…"}` (`core/views.py:377-381`). Correct, but clients
  mapping "already done" to 409 should expect 404 here.
- **R7 — Runs.** `DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test
  api core` → 111 tests OK (13 Sep 2026 run); attendance-focused subsets
  (11 double-clock/overlap/clock-out tests + 19
  correction/swap/audit tests) all PASS. No dev servers started; no tracked
  files modified.
