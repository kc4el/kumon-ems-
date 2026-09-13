# Review round 5 — 02 Employees

Scope: CRUD, soft-delete/resign + `deauthed` flag, search params, `page_size`,
onboarding role/dept persist, offboard flow, directory live render.
Branch `chore/standard-format` @ `64827c5`. No dev server started per task
constraints — "curl-equivalent" verification is via DRF `APIClient` in the
committed tests (same HTTP surface) plus static tracing of the fetchers.

Test runs (`DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test`):
- 17 employee `ApiTests` (list/create/delete/search/page_size/deauth): **OK** (29.5s;
  the `Exception: boom` log line is the expected fail-open test).
- `core.tests` (19, incl. `PaginationOrderingTests`, `PurgeResignedTests`): **OK**.
- 7 purge-run/auth/summary `ApiTests`: **OK**. Total 43 run, 0 failures.

## Verified working (evidence)

- **Create + validation contract.** 201 persists employee + provisions Supabase
  user (`api/tests.py:183-198`, `core/views.py:173-199`); duplicate email
  (case-insensitive) → 409 without Supabase call (`:242-256`,
  `core/views.py:167-171`); missing/invalid email → 400 (`:224-239`,
  `core/views.py:143-166`); upstream failure → 502 with no orphan row and no
  spurious rollback delete (`:259-274`, `core/views.py:200-218`); race
  `IntegrityError` → 409 (`:323-342`); `date_hired` read-only (`:453-472`,
  `core/serializers.py:45`); weak password → 400 pre-Supabase (`:822-834`).
- **List ordering + pagination.** `last_name, first_name` ordering
  (`api/tests.py:61-71`, `core/views.py:116`,
  `core/tests.py:147-150`); `?page_size=50` returns all 11 rows
  (`api/tests.py:73-82`) via `StandardResultsSetPagination`
  (`core/pagination.py:4-7`, `kumon_ems/settings.py:185-186`, max 100).
- **Search params.** `?search=` matches first/last/email, `?is_active=`,
  `?department=` (iexact) all tested (`api/tests.py:84-130`,
  `core/views.py:119-134`).
- **Soft-delete/resign + deauth.** DELETE → 200
  `{id, is_active:false, resigned_at, purge_on, deauthed}`, row kept,
  dashboard counts move 2 total / 1 active (`api/tests.py:490-509`,
  `core/views.py:230-262`); idempotent with single audit row (`:511-534`,
  `core/views.py:246-252`); Supabase `delete_user` called with employee id and
  `deauthed=True` in audit (`:537-550`); Supabase outage still resigns with
  `deauthed=False` fail-open (`:553-568`, `core/views.py:239-245`).
- **Purge as deauth retry.** `purge_resigned` removes only 30d+ resignations,
  dry-run keeps rows, Supabase failure keeps the row, success writes audit
  (`core/tests.py:169-247`, `core/management/commands/purge_resigned.py:28-51`);
  `/api/purge-run/` dry/real/invalid-days covered (`api/tests.py:910-972`,
  `core/views.py:801-830`).
- **Onboarding role/dept persist.** POST with `role` + department UUID persists
  both (`api/tests.py:201-221`); wizard reads `#onboardDepartment` /
  `#onboardRole`, resolves dept name→id, sends `role` before `•`
  (`static/js/dashboard.js:600-608`, `core/templates/core/index.html:3816,3829`).
- **Offboard flow.** Email → lookup → DELETE soft-delete; `deauthed:false`
  surfaces a distinct retry toast instead of false success
  (`static/js/dashboard.js:532-562`).
- **Directory live render.** Fetches `/api/employees/`, resolves department
  PK→name for `data-dept`, badge words (`Present Today`/`On Leave`) match
  `data-status` + `#statusFilter`, live cards carry expandable contact bodies,
  toolbar `#empSearch` filters, Slack button routes to chat tab
  (`static/js/dashboard.js:1485-1542, 469-492, 1093-1101`;
  `core/templates/core/index.html:397-421`).
- **Honesty states.** Promote/Transfer unwired actions disabled
  (`core/templates/core/index.html:1080,1136`, commit `2ba7d53`); exit-document
  uploads disabled with "not connected yet" copy (`:1294-1330`, commit
  `64827c5`).

## Bugs found (repro)

1. **Roster still truncated to 10 — main loader ignores `page_size`.**
   `loadEmployeeDirectory` fetches bare `/api/employees/`
   (`static/js/dashboard.js:1488`) while default page is 10
   (`kumon_ems/settings.py:186`). Repro: create 11 employees, open directory —
   the 11th never renders; typing their name in `#empSearch` can't help: the
   input is DOM-only (`dashboard.js:473,484`) and never calls the tested
   `?search=` param. The `page_size` fix (commit `3a487d6`) only helped the
   secondary fetchers.
2. **Offboard lookup truncated at 50 + no roster refresh.** Lookup uses
   `?page_size=50` (`dashboard.js:541`) → staff #51+ get "No employee found".
   On success there is no `loadEmployeeDirectory()` (unlike onboarding,
   `:630`), so the resigned person stays listed until manual reload.
3. **Resigned staff render as "On Leave".** Live cards map any
   `is_active:false` to `On Leave` (`dashboard.js:1512-1515`), and the
   serializer hides `resigned_at` (`core/serializers.py:32-45`), so resigned
   vs on-leave are indistinguishable; the server-side `?is_active=` filter is
   not wired to any toolbar control.
4. **PATCH email collision still inconsistent (plan item 13 open).**
   `EmployeeDetailView` has no `perform_update` (`core/views.py:221-262`):
   exact-case dup → 400 via auto `UniqueValidator` (create path returns 409);
   case-variant dup (`JANE@x` vs `jane@x`) skips the validator →
   `IntegrityError` → unhandled (non-DRF exc, `core/exception_handler.py:5-7`
   returns `None`) → 500.
5. **`showToast` still drops `type` (plan item 9 open).** Definition takes only
   `message` (`dashboard.js:841-856`); the type-aware fallback (`:1430-1449`)
   is dead code — its `typeof window.showToast !== 'function'` guard is false
   because the function declaration is hoisted. Error and success toasts are
   visually identical.
6. **Onboarding residuals.** Single-word name → `last_name:''` → 400, but the
   `typeof data.error === 'string'` check (`:616-621`) swallows dict field
   errors into a generic toast (plan item 12 open); dept lookup hits only page
   1 of `/api/departments/` (`:604`) and silently sends `department: NULL`
   on no-match; option drift vs directory filters — onboard offers
   "Human Resources"/"Design & UX" (`index.html:3817-3821`) while `#deptFilter`
   offers "HR" with no "Human Resources" (`:398-406`), and onboard roles
   (`:3829-3835`) match no `#roleFilter` option (`:407-415`); Manager / Start
   Date / IT assets still collected but discarded.
7. **Directory dept map is page-1-only** (`dashboard.js:1498-1501`): with >10
   departments, unmapped rows get `data-dept=''` and the dept filter misses
   them. Same first-page hazard as bug 6.
8. **Minor:** live-card "View Full Profile" just re-switches to the current
   directory view (`dashboard.js:1530`); `#statusFilter` "Probation" is
   unmatchable by any live row; roster has no loading/empty/inline-error
   states, catch is toast-only (`:1537-1541`, plan item 15 open).

## Regressions vs plan (`docs/review-employees/COMPILED.md` items 1-15)

- Fixed since plan: 1 (disabled promote/transfer), 3 (dept PK→name),
  4 (status words), 7 (expandable live cards), 8 (resign deauth + purge
  retry), 14 (honest upload state); 6 partial (Slack routes to chat, but
  profile button is a no-op).
- Partially fixed: 2 (role/dept persist; manager/start/assets still dropped),
  5 (`page_size` honored API-side, but main roster fetcher + offboard lookup
  still truncate — bugs 1-2), 10 (server params tested + toolbar input exists,
  but toolbar never calls `?search=` — bug 1), 11 (`deauthed:false` toast
  added, but still no refresh/confirm — bug 2).
- Still open, unchanged: 9 (bug 5), 12 (bug 6), 13 (bug 4), 15 (bug 8).
- **No regressions introduced:** all previously-passing employee/purge/
  pagination tests still pass (43/43); stable-ordering contract intact
  (`core/tests.py:137-166`).
