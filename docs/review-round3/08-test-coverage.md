# 08 — Test Coverage & QA (47 tests: 13 core + 34 api)

## Coverage map (route → test)
| Route | Covered |
|---|---|
| `dashboard-summary/`, `departments/` GET, `employees/` GET/POST/DELETE, `attendance/` POST, `attendance/clock-out/` 400s, `leaves/` GET/POST/PATCH-status, `shift-rosters/` POST, `payroll-items/` POST/PATCH, `performance/` GET, `audit-logs/` GET, `auth-token/`, `session-login/logout/`, `/`, `/login/`, static | Yes |
| `messages/`, `claim-statuses/` (POST/GET/filter/`perform_create`) | **None — 0 tests** |
| `ExpenseClaim` model/serializer/views (unwired in `api/urls.py`) | **None — dead code, 0 tests** |
| Detail routes: `departments/<pk>/`, `employees/<pk>/` GET/PUT, `attendance/<pk>/` PUT/DELETE, `shift-rosters/<pk>/`, `payroll-runs/` POST + `<pk>/`, `payroll-items/<pk>/` DELETE, `performance/<pk>/` POST/PUT, `leaves/<pk>/` DELETE | **None** |
| `auth-token` logout/revocation, token expiry | **None** (token has no expiry; logout only clears session) |
| Clock-out happy path, 404-no-open-row, 409-multi-open via API | **None** (only 400-validation + model-layer IntegrityError) |
| Payroll PATCH without `base_pay`, invalid `deductions` type | **None** |
| Shift PUT overlap-exclude-self, NULL work_date/employee skip | **None** |
| `MessageSerializer` text-or-attachment validator, `ClaimStatus` null-`claim_id` | **None** |
| Purge: `--days 0/custom`, boundary day-30, CASCADE payroll wipe, per-employee txn | **None** (happy/dry-run/fail-keep/negative-days/audit only) |

## Test quality
- Strong: exact-body assertions (`dashboard-summary` dict, `net_pay 950.00/900.00`, soft-delete idempotency `first==second`, shift 409+`{error}` envelope, purge audit-count==1).
- Weak: `list_endpoints` asserts only `results==[]` (no schema/pagination-shape); `throttle_rates_are_configured` asserts settings strings, never fires 429; page tests assert marketing strings, not wiring.
- Mock honesty: Supabase mocks honest (`assert_not_called` on 400/409; rollback asserts no orphan delete). Dishonest: `test_attendance_race_maps_to_409` patches `transaction.atomic` and calls `perform_create(serializer=None)` — never touches DB/serializer; two "second open rejected" tests assert model `IntegrityError`, not the API's 404/409 branches. Rollback test covers only create-raise, not success-then-save-fail (comment admits gap).

## Missing gates
- No coverage tool/threshold (`coverage.py`, `--fail-under`), no CI workflow, no JS tests (`dashboard.js` ~1000 lines untested), no e2e (login→CRUD→purge), no load/security tests (throttle, 429, auth brute-force).
- Regression note: purge fail-open from round-2 is FIXED (fail-closed + audit); `purge --dry-run` output and negative-`--days` now tested — not repeated as findings.

## Verdict
Good fast-path/409 coverage for employees/attendance/shifts/payroll; entire messages/claims/ExpenseClaim surface + all detail-route mutations + clock-out success branches untested. Add API tests for `messages/`, `claim-statuses/`, clock-out 200/404/409, payroll PATCH-no-base, detail CRUD; add coverage gate (≥80%) + one JS smoke test.
