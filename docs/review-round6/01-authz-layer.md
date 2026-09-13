# Review round 6 — 01: NEW authorization layer (`core/permissions.py` + view scoping)

Scope: the new owner-scoping layer only — `core/permissions.py` (75 lines),
its 12 `OwnerQuerysetMixin` list views + 11 `IsOwnerOrStaff` detail views,
the T1 `Employee.user` link + 0019 backfill, staff bypass, list-vs-detail parity.
Branch `chore/standard-format` @ `ca7a4f6`. No servers started; all findings
exercised via the Django test runner.

Baseline: `api.tests.OwnerScopingTests` + `api.tests.EmployeeUserLinkTests` —
9 tests, all pass (confirm scoping exists for the two shapes they cover:
employee-patch, leave list/detail, correction detail, notification mark-read).
They do **not** cover create-path scoping, approval writes, unscoped views,
unlinked users, or null-employee edges — that is where everything below lives.

Executable repro: `docs/review-round6/probes/tests.py` (39 tests, all pass
against current code — each asserts the *vulnerable* behaviour, so a failure
after a fix means the issue is closed). Run:

    DB_HOST= TZ=UTC PYTHONPATH=<repo>/docs/review-round6 \
      ./.venv/Scripts/python manage.py test probes

Probe tags below (`PROBE:<name>`) are the `print` lines that test emits.

## Scoping inventory (what the layer does cover)

List views with `OwnerQuerysetMixin` (12): employees (`core/views.py:125`,
lookup `"user"`), attendance (`:318`, default `employee__user`), corrections
(`:343`, `attendance__employee__user`), leaves (`:464`), allocations (`:475`),
overtime (`:548`, default), rosters (`:613`, default), swaps (`:624`,
`__swap_parties__`), payroll-items (`:737`, default), performance (`:772`,
default), expense-claims (`:855`, default), notifications (`:866`, default).
Detail views with `IsAuthenticated + IsOwnerOrStaff` (11): employees (`:254`),
attendance (`:330`), corrections (`:351`), leaves (`:469`), allocations
(`:489`), overtime (`:574`), rosters (`:618`), swaps (`:630`), payroll-items
(`:763`), performance (`:777`), expense-claims (`:860`).
Verified working, not re-reported: staff bypass both layers
(`permissions.py:47-48`, `:65-66`); swap-party OR parity list-vs-detail
(`permissions.py:29-38` vs `:70-74`); correction attendance-chain parity
(`:23-28` vs `views.py:348`); stranger denied on swaps (`PROBE:swap-stranger`
→ 403); both parties keep list visibility after approval
(`PROBE:swap-visible-A/B`); null-employee rows hidden from non-staff lists.

## A. Create-path IDOR — any authenticated user can create rows owned by anyone (HIGH)

No `ListCreateView` constrains the `employee`/`attendance`/roster FK to the
request user's employee (only `OvertimeSlipListCreateView.perform_create`,
`views.py:552-571`, checks the *pair* is consistent — not that it is *yours*).
Serializers take `employee` as a writable FK (`serializers.py:48-51,108-121,`
`137-144,147-160,163-166,194-205,239-246,249-252,255-267`). So user B POSTs a
leave with `{"employee": <A-id>}` → 201; the row lands in A's list, fires A's
notifications (correction/overtime/swap-decide create `Notification`s for the
row owner), and can trip pending-guards that block the victim's own legitimate
writes (e.g. a stranger's pending `ShiftSwap` on A's rosters makes A's own
swap POST 409 via `serializers.py:222-229`).
Repro (all return 201, `probes/tests.py::CreateAsOtherProbes`):

    POST /api/leaves/               {"employee": "<victim>", ...}  # PROBE:create-leave-as-other:201
    POST /api/attendance/           {"employee": "<victim>", "date": ...}
    POST /api/expense-claims/       {"employee": "<victim>", ...}
    POST /api/performance/          {"employee": "<victim>", ...}
    POST /api/payroll-items/        {"payroll_run": ..., "employee": "<victim>", "base_pay": ...}
    POST /api/leave-allocations/    {"employee": "<victim>", ...}
    POST /api/shift-rosters/        {"employee": "<victim>", ...}
    POST /api/overtime/             {"employee": "<victim>", "attendance": "<victim-att>"}
    POST /api/attendance-corrections/ {"attendance": "<victim-att>", ...}   # needs valid window (see A-note)
    POST /api/shift-swaps/          as a third user naming two strangers' rosters

A-note: the correction probe initially returned 400 only because my timestamps
put `proposed_clock_in` after `clock_out` (`serializers.py:101-104`); with a
valid window it is 201 (`PROBE:create-correction-on-other:201`).
Fix: in each `perform_create`, resolve `request.user.employee_profile` and
force/validate `employee` against it (403 on mismatch); same for
`attendance`/`requester_roster` ownership on corrections/overtime/swaps.

## B. No staff-only write gate — owners approve/edit their own rows (HIGH)

`IsOwnerOrStaff` (`permissions.py:42-49`) grants *write* to any owner, and no
detail view narrows `status`/pay/score fields to staff. Every `status` field
is serializer-writable (`serializers.py:108-121,147-160,66-78,194-205,`
`255-267`; performance is `__all__`, `:249-252`). Live-verified, all 200:

- B1 leave self-approve: `PATCH /api/leaves/<own>/ {"status":"Approved"}` →
  200, row Approved (`LeaveRequestDetailView`, `views.py:469-472`).
- B2 expense self-approve: same shape (`views.py:860-863`).
- B3 overtime self-approve: same shape (`views.py:574-577`). (Mitigating
  quirk: `perform_update`, `:579-582`, silently drops everything but `status`,
  so employee/attendance reassignment via PATCH is ignored — good accident,
  confusing API.)
- B4 correction self-approve **executes privileged side effects**:
  `PATCH .../attendance-corrections/<own>/ {"status":"Approved"}` rewrites the
  victim-attendance row, writes audit + notification (`views.py:373-404`).
  `PROBE:correction-self-approve:200`.
- B5 payroll self-raise: `PATCH /api/payroll-items/<own>/
  {"base_pay":"99999.00"}` → 200, `net_pay` recomputed to 99999.00
  (`views.py:763-769`; `base_pay`/`deductions` writable, only `net_pay`
  read-only, `serializers.py:239-246`).
- B6 performance self-edit: `PATCH /api/performance/<own>/ {"score":5,...}` →
  200 (`views.py:777-780`).
- B7 swap self-approve: requester `PATCH /api/shift-swaps/<id>/
  {"status":"Approved"}` → 200 and rosters actually swap holders
  (`views.py:652-683` via `_approve_swap`, `:686-724`). No counterparty or
  staff requirement; the requester approves their own request.
- B8 roster/attendance direct edit bypasses workflows: owner PATCHes own
  roster (`shift_type`, `:618-621`) or own `clock_in` (`:330-333`; serializer
  `validate` only guards create, `serializers.py:57-63`) — the correction
  workflow (`B4` path with audit/notification) is optional.
  (`PROBE:attendance-direct-edit:200`, `PROBE:roster-self-edit:200`.)
- B9 employee self-deactivate + role self-assign: `PATCH
  /api/employees/<own>/ {"role":"Chief","is_active":false}` → 200
  (`serializers.py:32-45` leaves both writable). `is_active=false` via PATCH
  skips the whole resign path (no `resigned_at`, no deauth, no audit —
  `views.py:264-315`), leaving an inactive row with live credentials.
Fix: split read-ownership from write-approval — staff-only (or
counterparty-only for swaps) for `status` transitions, pay fields, scores,
roster assignment edits; make `role`/`is_active` staff-only on PATCH.

## C. Correction PUT bypasses the decision guard entirely (HIGH)

`ShiftSwapDetailView.put` is explicitly routed through `patch`
(`views.py:645-650`, "The default update path would save the status field
directly, bypassing all of that") but `AttendanceCorrectionDetailView` got no
equivalent: it defines only `patch` (`:356`), so PUT takes the default
`UpdateModelMixin` path. `PUT .../attendance-corrections/<own>/` with
`{"status":"Approved", ...}` → 200, row marked Approved, attendance row
**untouched**, no audit log, no notification (`PROBE:correction-put-bypass`).
State desync in the other direction from B4: B4 applies without authority,
C approves without applying. Fix: mirror the swap view — route PUT through
the guarded `patch`.

## D. Views left unscoped (HIGH/MEDIUM)

Default permission is `IsAuthenticated` (`kumon_ems/settings.py:182-184`), so
anything without an explicit mixin/permission is open to every employee:

- D1 departments LC + detail (`views.py:115-122`): any employee can
  POST/DELETE departments. `PROBE:dept-create:201`, `PROBE:dept-delete:204`.
- D2 payroll-runs LC + detail (`views.py:727-734`): any employee can
  POST/DELETE payroll runs. `PROBE:payrollrun-create:201`,
  `PROBE:payrollrun-delete:204`.
- D3 `AttendanceClockOutView` (`views.py:407-461`): `employee_id` comes from
  the request body with zero ownership check — anyone clocks out anyone.
  `POST /api/attendance/clock-out/ {"employee_id":"<victim>"}` → 200 and the
  victim's row is closed (`PROBE:clockout-other:200`). Also accepts malformed
  ids into `filter(employee_id=...)` (500 class, cf. D6).
- D4 `LeaveBalanceView` (`views.py:518-545`): `?employee=<any-uuid>&year=`
  returns anyone's balances. `PROBE:balance-of-other:200` (allocated 7.0 for
  the victim).
- D5 `ShiftConflictView` (`views.py:585-610`): same shape — victim roster +
  approved leave reflected to the attacker.
  `PROBE:conflict-of-other:200` with one conflict row.
- D6 `LeaveBalanceView`/`ShiftConflictView`/`AttendanceClockOutView` pass raw
  query/body strings into UUID/date filters: `?employee=nope` raises
  unhandled `ValidationError: '"nope" is not a valid UUID'` → HTTP 500
  (`views.py:535`; `PROBE:balance-garbage:raises-unhandled-500`). Validate
  params → 400.
- D7 `EmployeeAuditLogListView` (`views.py:783-785`): any employee lists all
  audit rows, including other employees' resign/purge entries.
  `PROBE:audit-leak:200:True`.
- D8 `MessageListCreateView` (`views.py:818-829`): conversation is a
  client-supplied query param; any user reads any conversation, and
  `perform_create` reads `conversation_key` straight from `request.data`
  even though the serializer declares it read-only (`serializers.py:298-304`)
  — writable despite the schema. `PROBE:message-cross-read:200:True`.
- D9 `ClaimStatusListCreateView` (`views.py:832-852`): `claim_id` is
  client-controlled with get-or-create-then-overwrite semantics — any user
  flips any claim's status. `PROBE:claim-hijack:200:Approved`.
- (Intentional, no change: `DashboardSummaryView` AllowAny `:79-83` is
  documented as public aggregates; `SessionLogin/LogoutView` `:788-815`;
  `PurgeRunView` IsAdminUser `:882-883`.)
Fix: staff-only for D1/D2/D7; force `employee=request.user`'s employee (or
staff-only-others) on D3/D4/D5 with param validation (D6); per-membership
conversation ACL or remove cross-conversation read (D8); own-claims-only or
staff gate (D9).

## E. Authenticated non-staff can mint employee rows + Django accounts (MEDIUM)

`EmployeeListCreateView.post` (`views.py:155-251`) runs for any authenticated
caller (`get_permissions`, `:148-153`, only special-cases anonymous). The
role-strip (`payload.pop("role")`, `:167`) and duplicate-email 409 apply only
to anonymous; an authenticated non-staff POST keeps `role`, sets any email,
and — if `password` is supplied — mints a real Django `User`
(`:212-221`). Verified: non-staff POST → 201, row has `role="Manager"` and a
linked login-capable user (`PROBE:employee-mint`,
`PROBE:employee-mint-role:Manager:user=True`). Employee creation should be
staff-only; self-signup is the anonymous path.
Related hygiene: `perform_destroy` (`:259-262`) is dead code — the `destroy`
override (`:264-315`) never calls it; and any owner can DELETE their own row,
i.e. self-resign kills their own Django user/tokens/sessions (`:283-294`
match by `email__iexact`, so it also kills a same-email account the resigner
does not own — acceptable here, but note the match key is email, not the
`user` FK).

## F. Unlinked users are write-only ghosts (MEDIUM)

A `User` with no `Employee` row (the permanent state of every 0019 orphan,
§H) matches nothing in any scoped list, but §A still lets them POST as anyone
while detail reads 403: ghost POST leave-as-victim → 201, ghost list → `[]`,
ghost detail → 403 (`PROBE:ghost:create=201:list_sees=0:detail=403`;
`PROBE:ghost-employee-list:0`). Capping creates per §A closes this; consider
also rejecting writes from users with no `employee_profile`.

## G. `owns_object` / list-vs-detail edge cases (LOW-MEDIUM)

- G1 overtime dual-parent split (live): `OvertimeSlip` has both `employee`
  and `attendance` FKs (`models.py:72-90`). List scopes only on
  `employee__user` (default lookup, `views.py:548-550`) but `owns_object`
  also accepts the attendance chain (`permissions.py:23-28`). A slip with
  `employee=A, attendance.employee=B` (creatable via ORM/admin/import, not via
  the view's `perform_create` guard) is invisible to B in the list yet GETs
  200 on detail (`PROBE:ot-mismatch:list=False:detail=200`). Fix: scope the
  list on `Q(employee__user=...) | Q(attendance__employee__user=...)`, or
  enforce equality at the model level (`clean()`/constraint), not just the view.
- G2 swap null-side (live, behaves sanely — documented, no fix demanded):
  `ShiftRoster.employee` is nullable (`models.py:150-152`). A swap with one
  null side is visible to the other party (either-side OR, `permissions.py:29-38`;
  `PROBE:swap-null-side-detail:200`) but approval correctly 400s
  (`views.py:694-695`; `PROBE:swap-null-side-approve:400`). Note the flip side:
  post-approval, roster holders change, so each party's visibility derives
  from the *current* holders — verified both parties still see the swap after
  decide (`PROBE:swap-visible-A/B`); fine today, fragile if rosters are later
  unassigned (row goes staff-only, parties lose their own swap history).
- G3 anonymous falls through to the full queryset (`permissions.py:65-66`
  returns `qs` when the user is not authenticated). Currently unreachable —
  every mixed-in view inherits `IsAuthenticated` except the employee POST,
  which never touches `get_queryset` — but one future `AllowAny` list reuse
  turns it into a full-table leak. Fix: return `qs.none()` for anonymous.
- G4 `is_staff` is the only bypass bit: a superuser without `is_staff` is
  scoped like a regular employee, and `NotificationMarkReadView` (`views.py:871-879`)
  re-implements its own staff check instead of reusing `owns_object` (same
  verdict today, two copies to keep in sync). Minor: unify on the helper.
- G5 error-code split aids enumeration slightly: non-owner detail → 403 via
  DRF, but mark-read forges a 404 (`views.py:876`). Pick one (404 hides
  existence).

## H. T1 link + 0019 backfill orphan classes (MEDIUM/LOW)

- H1 anonymous signup without `password` creates a Django-orphan employee:
  the `User` link is only created `if password:` (`views.py:212-221`), so a
  passwordless signup (Supabase user + `Employee(user=None)`) → 202, row
  permanently invisible/unusable over Django session/token auth, since both
  layers key on `employee.user` (`permissions.py:17-22,60-75`).
  `PROBE:signup-no-pwd:202:user=None`. Either always mint the link or document
  that passwordless signups are Supabase-only.
- H2 backfill matches `User.email` only (`migrations_compat.py:26-31`): an
  account whose email lives in `username` with a blank `email` field never
  links (`PROBE:backfill-username-only:matched=0:linked=False`), and rows
  already (mis)linked are skipped forever (`user__isnull=True`, `:31`) with
  no report of which users were left behind. Consider also matching
  `username__iexact` when it looks like an email, and logging unmatched
  usernames in the migration output.
- H3 no nested routes exist (`api/urls.py` is flat UUID detail paths), so the
  nested-route probe surface is the ownership *chains* instead — correction→
  attendance→employee and slip→attendance→employee (G1) and swap→roster→
  employee (G2) — all covered above.

## Suggested fix order

1. §A create-ownership + §F ghost writes (one `perform_create` guard pattern
   kills both, including D3/D8/D9's write halves).
2. §B staff/counterparty write gates + §C correction-PUT routing (one-line).
3. §D staff-only/read-own on D1/D2/D4/D5/D7 + D6 param validation.
4. §E staff-only employee creation; §B9 staff-only `role`/`is_active`.
5. §G1 overtime parity, §G3 `qs.none()`, §H link/backfill follow-ups.
