# Plan: FrappeHR-mirrored Company settings, Kumon design kept (`2026-09-17`)

## Goal

Reorganize Company settings into FrappeHR HR-Settings groups (Leave, Shift, Payroll, Mobile, System) where every toggle actually enforces, reusing Kumon tokens only.

## Current context / assumptions

- Repo `C:/Users/mikae/OneDrive/Desktop/Codes/transit-planner/kumon-ems-`, branch `feat/settings-view`, suite 297 green. Run python as `DB_HOST= ./.venv/Scripts/python`.
- FrappeHR HR Settings (docs.frappe.io/hr/hr-settings) groups: 1 Employee, 2 Payroll (working-days basis, max hours vs timesheet, holidays-in-days, rounded total, half-day fraction, slip email/encrypt), 3 Shift (allow multiple assignments same date), 4 Leave (approver mandatory, backdated restrict, auto-allocate by policy, encashment), 5 Hiring, 6 Mobile (allow check-in from mobile app). Repo-local `docs/frappehr-comparison.md` confirms the overlap map.
- Overlap verdict (enforceable in Kumon only): Shift 3.1 → double-booking toggle; Leave 4.6 → backdated toggle; Leave 4.7 → auto-allocate days; Payroll 2.2 → OT max already exists, keep; Payroll 2.4 → round-net toggle; Mobile 6.1 → check-in toggle. Dropped honestly: approver-mandatory (zero `approver` matches in models/views/docs — no concept to toggle), holidays-in-days (no Holiday table), encashment, hiring/vacancy (no staffing plan), slip email/encrypt (no mail flow).
- Enforcement points verified: overlap guard `core/serializers.py:326-334`; leave `validate()` end of `LeaveRequestSerializer.validate` (`core/serializers.py:~205`, after the end<start check); payroll net `core/views.py:1113` (`serializer.save(net_pay=base - deductions)`); check-in POST `core/views.py:502`, self-service POST `AttendanceSelfView.post` (~:710); `SiteSetting` reader `_site_val` + `SITE_SETTING_SPECS` in `core/serializers.py`, `SITE_SETTING_DEFAULTS` duplicated in `core/views.py` (update both + comment).
- Design law (unchanged): `page-title-block`, `pill-tabs/tab-pill` (`main.css:325-355`), `white-card/card-title/card-sub` (`:574-596`), `input-cell` + UPPERCASE label + `penpot-input/penpot-select-full`, `inputs-2grid`, `modal-foot` + `btn-outline-gray/btn-navy-cta`, `:root` vars only, `showToast`, existing `switchView/breadcrumb/loadSettingsView` pattern. Zero new CSS.

## Architecture / proposed approach

Five new `SiteSetting` keys (all default = current behavior, so zero behavior change until staff flips one) each read at the exact enforcement point that today hardcodes the FrappeHR-default side. Company pane keeps its pill + cards but regroups inputs under five `white-card` sections mirroring FrappeHR groups; dead inputs (`setAttGrace/setLeaveQuota/setPayAdvanceMax`) deleted; OT min/max moves under Payroll (FrappeHR 2.2). Role hardening (SEC-H1, still open) rides along as T0.

## Step-by-step tasks

### T0 — Safety: role out of self-service (carried, still open)
`core/serializers.py:542`: `MUTABLE_PROFILE_FIELDS = ("first_name", "last_name", "email")`. `index.html` `setRole` (~:3595): add `disabled` + note "Role is assigned by HR." `dashboard.js` `saveSettingsProfile`: drop `role` from payload + confirm text "name and email".
Test first: new `api/test_settings_role.py` — PATCH `{profile:{role:"hr"}}` → 200, row unchanged.
Verify: FAIL before, OK after. Commit `fix: role read-only in self-service`.

### T1 — Register the 5 keys (specs + defaults + seeds)
`core/serializers.py` `SITE_SETTING_SPECS` += `{"leave_restrict_backdated": {"bool": True}, "leave_auto_allocate_days": {"min": 0, "max": 365, "integer": True}, "shift_allow_double_booking": {"bool": True}, "payroll_round_net": {"bool": True}, "mobile_checkin_enabled": {"bool": True}}`. `SiteSettingSerializer.validate` must accept `"true"/"false"` (case-insensitive) for bool specs. `SITE_SETTING_DEFAULTS` (serializers + `core/views.py:1422` + `core/models.py` `NUMERIC_RANGES` where numeric): backdated `"false"`, allocate `"0"`, double-book `"false"`, round-net `"false"`, mobile `"true"`.
Test first (append `api/test_settings_site.py`): PATCH each key valid → 200 + persisted; PATCH `leave_auto_allocate_days: "9999"` → 400; PATCH bool `"yes"` → 400.
Verify: FAIL before (ChoiceField rejects unknown key), OK after. Commit.

### T2 — Shift: double-booking toggle (FrappeHR 3.1)
`core/serializers.py` overlap guard (~:326): wrap — `if _site_val("shift_allow_double_booking").lower() != "true":` keep existing clash→409; when `"true"`, skip the check entirely (both create + update paths using this validator).
Test first: with default → overlapping POST → 409 (existing tests cover); set key `"true"` via ORM → same POST → 201; set back → 409.
Verify: new tests green + existing shift tests green. Commit.

### T3 — Leave: backdated toggle (FrappeHR 4.6)
`LeaveRequestSerializer.validate`, after the end<start check: `if start is not None and _site_val("leave_restrict_backdated").lower() == "true" and start < timezone.localdate(): raise serializers.ValidationError({"start_date": "Backdated leave applications are disabled."})`. (`timezone` already imported in serializers? check top — `from django.utils import timezone`; if absent, add.)
Test first: default → past start → 201; toggle on → 400 with key `start_date`; today/future → 201 either way.
Verify: green. Commit.

### T4 — Leave: auto-allocate on hire (FrappeHR 4.7, Kumon-simple)
`core/signals.py`: `@receiver(post_save, sender=Employee)` new fn — on `created`, read int `_site-like` value of `leave_auto_allocate_days` (import `SiteSetting` direct; default 0); if > 0: `LeaveAllocation.objects.get_or_create(employee=instance, leave_type="Vacation", year=timezone.localdate().year, defaults={"days_total": days})`. Single type+current year only (documented simplification of policy-based allocation).
Test first: with default 0 → hire creates zero allocations; set 14 → hire creates one Vacation row for this year; second save (update) creates none.
Verify: green. Commit.

### T5 — Payroll: round-net toggle (FrappeHR 2.4)
`core/views.py:1113`: `net = base - deductions`; → `if get_site_setting("payroll_round_net").lower() == "true": net = round(net, 2)`; `serializer.save(net_pay=net)`. (`get_site_setting` exists in views.py already.)
Test first: default → odd net stored exact (e.g. base 1000.005? use values producing 3 decimals — Decimal base/deductions with 3dp? fields allow? simpler: assert stored == base - deductions exactly); toggle on → stored == rounded.
Verify: green + existing payroll tests green. Commit. (T2–T5 may squash to one `feat: FrappeHR-mirror enforcement` if each green in sequence.)

### T6 — Mobile: check-in toggle (FrappeHR 6.1)
`AttendanceCheckInView.post` (`core/views.py:502`) top + `AttendanceSelfView.post` top: `if get_site_setting("mobile_checkin_enabled").lower() != "true": return Response({"error": "Mobile check-in is disabled by your administrator."}, status=403)`. Default `"true"` = today's behavior.
Test first: default → kiosk/self POST works (existing tests); set `"false"` → both 403 with that message; GET self unaffected.
Verify: green. Commit.

### T7 — Company pane regrouped (same tokens, FrappeHR sections)
`core/templates/core/index.html` Company pane: five `white-card`s — LEAVE RULES (backdated checkbox `setLeaveBackdated`, auto-allocate days `setLeaveAutoDays`), SHIFT RULES (double-booking checkbox `setShiftDouble`), PAYROLL RULES (`setOtMin/setOtMax` moved here + round-net checkbox `setPayrollRound`), MOBILE (`setMobileCheckin` checkbox + note "Gates kiosk + self-service clock-in"), SYSTEM (`setPurgeDays/setUploadCap`, throttle/CORS read-only, doors explainer). Delete `setAttGrace/setLeaveQuota/setPayAdvanceMax` blocks. `dashboard.js` `renderSettingsSite`/`saveSettingsSite`: read/write the 5 new ids (checkboxes → `"true"/"false"` strings), drop-nothing-else.
Test first: content asserts — 5 section titles present, 3 dead ids absent, new ids present in both files, save payload contains `shift_allow_double_booking`.
Verify: FAIL before, OK after, `node --check` clean. Commit.

### T8 — Full gate + commit
`DB_HOST= ./.venv/Scripts/python manage.py test` → 297 + ~10 new, zero failures; `black`/`isort`/`check`/`node --check` clean. Push only on explicit yes.

## Tests / validation

TDD per task: `api/test_settings_site.py` appends (T1–T6), `api/test_settings_role.py` new (T0), content asserts in `api/test_settings_frontend.py` (T7). Every toggle tested in both states (default-off behavior unchanged + flipped behavior). Final gate T8.

## Risks, tradeoffs, and open questions

- Auto-allocate covers Vacation/current-year only — FrappeHR does policy-based multi-type; simplification stated in UI sub-copy ("grants Vacation days for this year on hire") so the paper stays honest.
- Bool settings stored as `"true"/"false"` strings (SiteSetting.value is CharField) — reader normalizes `.lower()`; any other stored value behaves as false + logs (existing fallback).
- `shift_allow_double_booking=true` also relaxes the swap atomic re-check (same validator) — intended; note in commit.
- Mobile toggle gates kiosk too (shared POST logic) — intended; kiosk is the office tablet, message says "administrator" generically.
- Dropped FrappeHR items (approver-mandatory, holidays, encashment, hiring, slip mail) stay future work; the Company pane must not gain stub inputs for them (FE-H3 rule).
- Open: should staff see *who* flipped a toggle? `EmployeeAuditLog` already logs site changes (T11, landed) — covered.
