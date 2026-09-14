# API design & contract — review round 5

Scope: `api/urls.py` (39 `path()` entries), `core/views.py`, `core/serializers.py`,
`core/exception_handler.py`, `core/pagination.py`, `kumon_ems/settings.py` REST block.
Branch: `chore/standard-format`. Method: read-only static review + area tests
(`DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test api core`), no live writes,
no dev server.

Test evidence: `Ran 111 tests … OK` (api + core, 2026-09-12 run, ~142 s).

## Verified working (evidence)

### Route inventory — 39 paths in `api/urls.py`, 32 hit by tests
Full list with file+line (`api/urls.py`): `dashboard-summary/` (46–48),
`departments/` (49–53), `departments/<uuid:pk>/` (54–58), `employees/` (59),
`employees/<uuid:pk>/` (60), `attendance/` (61–63), `attendance/<uuid:pk>/` (64–68),
`attendance-corrections/` (69–73), `attendance-corrections/<uuid:pk>/` (74–78),
`attendance/clock-out/` (79–83), `leaves/` (84), `leaves/<uuid:pk>/` (85),
`leave-allocations/` (86–90), `leave-allocations/<uuid:pk>/` (91–95),
`leave-balances/` (96), `overtime/` (97–99), `overtime/<uuid:pk>/` (100–104),
`shift-rosters/` (105–109), `shift-rosters/conflicts/` (110–114),
`shift-rosters/<uuid:pk>/` (115–119), `shift-swaps/` (120–124),
`shift-swaps/<uuid:pk>/` (125–129), `payroll-runs/` (130–134),
`payroll-runs/<uuid:pk>/` (135–139), `payroll-items/` (140–144),
`payroll-items/<uuid:pk>/` (145–149), `performance/` (150–154),
`performance/<uuid:pk>/` (155–159), `audit-logs/` (160), `auth-token/` (161),
`session-login/` (162), `session-logout/` (163), `messages/` (164),
`claim-statuses/` (165–169), `expense-claims/` (170–174),
`expense-claims/<uuid:pk>/` (175–179), `notifications/` (180–184),
`notifications/<uuid:pk>/read/` (185–189), `purge-run/` (190).

Hit-by-test (all via `APIClient`, authed unless noted), expected codes asserted:
- `GET dashboard-summary/` → 200 anon + authed, exact aggregate body
  (`api/tests.py:30–38`, `:132–180`).
- 9 list endpoints return 200 `{"results": []}` paginated envelope
  (`api/tests.py:40–59`): departments, employees, attendance, leaves,
  shift-rosters, payroll-runs, payroll-items, performance, audit-logs.
- `POST auth-token/` → 200 `{"token": …}` (`api/tests.py:34–38`).
- `POST session-login/` → 200 + `sessionid` cookie, then `GET employees/` 200,
  `POST session-logout/` 200, then `GET employees/` 403
  (`api/tests.py:1113–1127`); wrong creds → 401 (`api/tests.py:1103–1111`,
  `core/views.py:725–727`).
- `POST employees/` → 201 happy path, role+department persisted
  (`api/tests.py:183–221`); missing email → 400, bad email → 400, no Supabase call
  (`api/tests.py:224–239`, `core/views.py:147–166`); duplicate (case-insensitive)
  → 409 (`api/tests.py:242–256`, `core/views.py:167–171`); race IntegrityError
  → 409 (`api/tests.py:323–342`, `core/views.py:200–205`); upstream throw → 502,
  no rollback delete when nothing created (`api/tests.py:259–274`,
  `core/views.py:206–218`); weak password → 400 (`api/tests.py:822–834`,
  `core/views.py:151–161`).
- `DELETE employees/<id>/` → 200 soft-delete body
  `{id, is_active:false, resigned_at, purge_on, deauthed}` — idempotent, single
  audit row, Supabase outage still resigns with `deauthed=false`
  (`api/tests.py:490–568`, `core/views.py:225–262`).
- `POST attendance/` duplicate → 409 `{error}` (`api/tests.py:276–289`,
  `core/serializers.py:57–62` fast path + `core/views.py:269–274` race path);
  race unit test raises `Conflict409` (`api/tests.py:300–306`).
- `POST attendance/clock-out/` → 400 no id / 400 bad datetime / 400 precedes
  clock-in; 404 none-open / 409 multi-open branches exist
  (`api/tests.py:344–394`, `core/views.py:349–403`).
- `POST/ PATCH shift-rosters/` overlap → 409 `{error}`; adjacent OK;
  cross-employee same slot OK; start≥end → 400
  (`api/tests.py:570–664`, `core/serializers.py:155–178`).
- `POST/ PATCH shift-swaps/` → 201 Pending; same-employee → 400; diff-date →
  400; second pending on same roster → 409; approve swaps holders + 2
  notifications; approve-causing-overlap → 409 with rows unchanged + status stays
  Pending; same-date overlapping pair approve succeeds; reject notifies;
  re-decide closed → 409 (`api/tests.py:1260–1485`,
  `core/serializers.py:194–217`, `core/views.py:577–649`).
- `POST payroll-items/` duplicate → 409; PATCH recomputes `net_pay`;
  client `net_pay` ignored (`api/tests.py:396–451`,
  `core/views.py:668–693`, `core/serializers.py:226–233`).
- `POST leave-allocations/` → 201; duplicate → 409 `{error}`
  (`api/tests.py:986–1019`, `core/views.py:420–427`; DB
  `unique_together (employee, leave_type, year)`, `core/models.py:124–126`).
- `GET leave-balances/?employee=&year=` → 200 balances math, defaults
  `Vacation/Sick=5`, missing/bad params → 400
  (`api/tests.py:1035–1099`, `core/views.py:458–485`).
- `GET shift-rosters/conflicts/?employee=&date=` → 200 `{date, conflicts[]}`;
  missing params → 400 (`api/tests.py:876–908`, `core/views.py:520–545`).
- `POST overtime/` hours server-computed (`hours` read-only,
  `core/serializers.py:134–147`), incomplete/other-employee/missing attendance
  → 400 `{error}`; approve PATCH → 200 (`api/tests.py:1130–1229`,
  `core/views.py:488–518`).
- `POST attendance-corrections/` → 201 row untouched; empty/inverted → 400;
  approve PATCH applies times (other fields ignored) + audit + notification;
  reject changes nothing (`api/tests.py:1513–1604`, `core/views.py:294–346`,
  `core/serializers.py:80–105`).
- `POST claim-statuses/` upsert idempotent → 200 single row; empty/blank/unknown
  → 400 (`api/tests.py:713–748`, `core/views.py:755–775`,
  `core/serializers.py:308–322`).
- `POST messages/` sender bound to request user, `conversation_key` defaults to
  `general` (`api/tests.py:695–711`, `core/views.py:748–752`).
- `GET notifications/` + `PATCH notifications/<id>/read/` → 200 `is_read=true`
  (`api/tests.py:836–854`, `core/views.py:788–798`).
- `POST purge-run/` non-staff → 403; staff dry-run counts, real deletes+audits,
  non-int days → 400 (`api/tests.py:910–974`, `core/views.py:801–830`,
  `permission_classes=[IsAdminUser]` line 802).
- Auth default deny: anon `GET employees/`, `GET expense-claims/`,
  `GET leave-allocations/`, `GET attendance-corrections/`, `GET overtime/` →
  403 (`api/tests.py:30–33, 750–752, 1021–1023, 1541–1543, 1227–1229`;
  default `IsAuthenticated`, `kumon_ems/settings.py:182–184`).

### Error envelope — uniform `{error}` on failures (tested)
- `core/exception_handler.py:4–26` (`EXCEPTION_HANDLER` wired at
  `kumon_ems/settings.py:192`): passthrough if already `{error}` (11–12);
  `{detail}` → `{error}` incl. `not_authenticated` → `"Authentication required."`
  (13–19); field errors flattened to `"; "`-joined `{error}` string (21–25).
- Asserted `set(body.keys()) == {"error"}` for: anon 403, leaves 400
  (`api/tests.py:291–298`), attendance 409 (`:289`), shift overlap 409 (`:593`),
  allocation 409 (`:1019`), overtime 400s (`:1178,1210,1225`), swap 400/409s
  (`:1289,1330,1463`). 409 bodies from `Conflict409`
  (`core/exceptions.py:4–7`, status 409) flow through the `{detail}→{error}`
  mapping, so all six 409 producers share one envelope.

### 409 rule — DB + serializer + view triple lock (tested per-rule)
| Rule | Enforcer | Test |
|---|---|---|
| Employee email dup (ci) + race | `core/views.py:167–171,200–205`; `email unique`, `core/models.py:31` | `api/tests.py:242–256,323–342` |
| Attendance 1/day + 1-open | serializer fast path `core/serializers.py:57–62`; view race `core/views.py:269–274,281–286`; `unique_together`+`UniqueConstraint one_open_attendance_per_employee`, `core/models.py:53–61` | `api/tests.py:276–306` (+ DB constraint `:308–320`) |
| Clock-out multi-open | `core/views.py:382–386` | branch present; second-open DB behaviour `:348–362` |
| Leave allocation dup | `core/views.py:420–427` (+ `validators=[]` comment `core/serializers.py:129–131`); `unique_together`, `core/models.py:125` | `api/tests.py:1004–1019` |
| Payroll line dup | `core/views.py:672–685` (+ `validators=[]` `core/serializers.py:231–233`); `unique_together`, `core/models.py:182` | `api/tests.py:396–412` |
| Shift overlap | `core/serializers.py:165–177` | `api/tests.py:570–593` (+ approve-rollback `:1361–1386`) |
| Swap pending dup / re-decide decided | `core/serializers.py:209–216` / `core/views.py:582–586` | `api/tests.py:1310–1330,1445–1463` |

### Pagination — params honoured where tested
- `StandardResultsSetPagination`: `page_size=10`, `page_size_query_param="page_size"`,
  `max_page_size=100` (`core/pagination.py:4–7`; wired
  `kumon_ems/settings.py:185–186`). `GET employees/?page_size=50` returns 11/11
  (`api/tests.py:73–82`); ordering stable for employees/shift-rosters/payroll
  (`api/tests.py:61–71`, `core/tests.py:137–166` asserts 5 view orderings).

### Throttle — configured + login exempt by design
- Defaults `AnonRateThrottle` + `UserRateThrottle`, rates `anon 100/day`,
  `user 1000/day` (`kumon_ems/settings.py:187–191`); asserted in
  `api/tests.py:689–693`. `SessionLoginView.throttle_classes = []` with comment
  that one office IP shares the anon quota (`core/views.py:711–716`).

### AllowAny — 4 surfaces, each narrowed
- `DashboardSummaryView` class-level `AllowAny` (`core/views.py:69–73`, comment
  cites B10 public counts). `SessionLoginView` `AllowAny`
  (`core/views.py:711–712`). `EmployeeListCreateView.get_permissions` returns
  `AllowAny()` for POST only, else default (`core/views.py:136–141`, self-service
  signup comment). `obtain_auth_token` (DRF default AllowAny,
  `api/urls.py:161`) reachable anon per `api/tests.py:34–38`. Everything else
  falls through to `IsAuthenticated`; `purge-run` further narrows to
  `IsAdminUser` (`core/views.py:802`).

## Contract violations found

1. **Success envelope split `{message}` vs `{error}`** — failures are `{error}`
   but three success bodies use `{message}`: clock-out
   (`core/views.py:396`), session-login (`:730`), session-logout (`:738`).
   Clients must branch on key by endpoint. Suggest `{message}`→`{detail}`-style
   success key or document the trio as the only exception.
2. **`POST claim-statuses/` returns 200 on create** (`core/views.py:759–763`
   overrides `create` with `status=HTTP_200_OK`). Upsert-idempotent by design
   (`:765–775` get_or_create), but first-time create is still 200, not 201 —
   breaks the list-create 201 convention every other `ListCreateAPIView` follows.
   Tested as 200 (`api/tests.py:736–748`), so the test locks the violation in.
3. **`DELETE employees/<id>/` returns 200, not 204** (`core/views.py:253–262`).
   Justified (soft-delete returns `purge_on`/`deauthed`), idempotent
   (`api/tests.py:524–532`) — but it is a REST deviation; keep only with docs.
4. **Field errors flattened, field identity lost** —
   `core/exception_handler.py:21–25` joins all field errors into one
   `{error}` string (`"start_time: …; end_time: …"`). Uniform envelope at the
   cost of machine-readable per-field errors; frontend cannot highlight the
   offending field without parsing. Deliberate (test `:291–298` asserts the
   flat key) but should be a documented tradeoff.
5. **Messages conversation default mismatch** — list defaults
   `?conversation=sarah` (`core/views.py:745`; model default also `"sarah"`,
   `core/models.py:224`) while create defaults missing key to `"general"`
   (`core/views.py:751`). A client posting without a key then listing without a
   key never sees its own message. One default should win.
6. **Login throttle fully disabled = brute-force surface** —
   `throttle_classes = []` (`core/views.py:716`) removes anon *and* user
   throttles from the credential endpoint; the comment defers hardening
   ("token-lifecycle work"). Shared-IP concern is real, but zero throttling on
   `authenticate()` with no lockout/captcha is the riskiest AllowAny surface.
   Minimum: scoped login throttle (e.g. 10/min/IP) rather than `[]`.
7. **409 rule has update-path holes** —
   - `EmployeeDetailView` (`core/views.py:221–223`) has no `perform_update`
     409 guard: PATCHing a duplicate `email` hits the DB `unique` constraint
     (`core/models.py:31`) as an unhandled `IntegrityError` → 500, not 409.
     Create path is guarded (`:167–171`); update is not.
   - `LeaveAllocationDetailView` (`core/views.py:430–432`) likewise has no
     update guard while create does (`:420–427`); PUT/PATCH colliding on
     `(employee, leave_type, year)` → 500, not 409.
   - `AttendanceDetailView.perform_update` maps to 409 (`:281–286`) but has **no
     direct test** (only create-path 409 is tested); same for roster-update
     overlap (serializer excludes `self.instance`, `:174–175`, but no PATCH
     overlap test).
8. **Status-only-update views silently ignore fields** — `OvertimeSlipDetailView`
   (`core/views.py:514–517`) and `ShiftSwapDetailView.perform_update`
   (`:567–575`) discard non-status fields on PUT/PATCH without 400. A client
   PUTting full objects gets 200 while most of the payload was dropped.
9. **Throttle 429 path untested** — only rates asserted
   (`api/tests.py:689–693`); no test forces 429, so the 429 body shape
   (`{error}` via handler) and `Retry-After` behaviour are unverified.
10. **Pagination ordering not universal** — `PaginationOrderingTests`
    (`core/tests.py:137–166`) pins 5 views; message ordering relies on model
    `Meta.ordering = ("created_at",)` (`core/models.py:233`) with second-level
    ties, and several list views' stability is asserted only statically.
    No test for `page_size > max_page_size` clamping (100) or invalid `page`.

## Missing surface

- **7 detail routes with zero test hits** (list views hit, detail never
  exercised): `departments/<uuid:pk>/` (`api/urls.py:54–58`),
  `attendance/<uuid:pk>/` (`:64–68`), `leave-allocations/<uuid:pk>/` (`:91–95`),
  `shift-rosters/<uuid:pk>/` (`:115–119`), `payroll-runs/<uuid:pk>/`
  (`:135–139`), `performance/<uuid:pk>/` (`:155–159`),
  `expense-claims/<uuid:pk>/` (`:175–179`). GET/PUT/PATCH/DELETE semantics
  (including hard- vs soft-delete — only employee DELETE is specified) are
  unverified on all seven.
- **No PUT coverage anywhere** — updates tested only via PATCH (leaves,
  payroll-items, overtime, swaps, corrections, notifications). PUT on
  `RetrieveUpdateDestroy` views (full-replace required fields?) is unspecified.
- **DELETE untested except employee** — department/attendance/leave/roster/swap/
  payroll/performance/expense-claim DELETE codes and cascade/audit side effects
  unknown.
- **Anon-denied asserted on only 5 routes** (employees, expense-claims,
  leave-allocations, attendance-corrections, overtime); ~20 other
  auth-required routes (departments, attendance, leaves, rosters, payroll,
  performance, messages, notifications, claim-statuses, leave-balances,
  conflicts, session-logout, purge-run-nonstaff-partial) rely on the global
  default without a per-route assertion.
- **Pagination params beyond one case** — only `employees/?page_size=50`
  tested. `?page=`, `page_size=1`, `page_size=101` (clamp to 100),
  `page_size=abc`, out-of-range page, and per-view `count/next/previous`
  envelope keys untested.
- **Claim-statuses has no detail route** — `ListCreate` only
  (`api/urls.py:165–169`); no GET/PUT/DELETE by `claim_id`, clients must
  list-and-scan. Upsert-by-POST covers writes, reads don't.
- **Notifications/messages surface gaps** — notifications: no create route
  (server-generated, correct) but also no DELETE/unread-toggle; mark-read is
  PATCH-only with ignored body (`core/views.py:793–798`), PUT/POST on the
  `…/read/` URL unspecified. Messages: no detail/delete, no attachment
  round-trip test (serializer supports `attachment`/`attachment_url`,
  `core/serializers.py:270–305`, untested over HTTP).
- **Auth edge gaps** — `POST auth-token/` invalid-creds shape, `POST
  session-logout/` anon (403 vs 200), and `purge-run` throttle interaction
  untested. `GET leave-balances/` with malformed UUID `employee` untested
  (only missing/non-int `year`, `api/tests.py:1068–1075`).
- **Filter params documented only for employees/messages** —
  `?search=&department=&is_active=` (`core/views.py:119–134`,
  `api/tests.py:84–130`) and `?conversation=` (`core/views.py:744–746`).
  No filtering/ordering params on any other list (e.g. rosters by
  employee/date, leaves by status/employee, payroll-items by run) — clients
  paginate-and-filter locally.
