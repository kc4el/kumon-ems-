# 05 — Payroll, Claims, Messages, Notifications, Purge, Conflicts (round 5 @ chore/standard-format)

Scope: payroll runs/lines + net derivation, `ExpenseClaim` vs `ClaimStatus`
wiring, messages/chat endpoints, notifications, `purge_resigned` dry-run +
deauth retry, `ShiftConflictView`. No dev server started; HTTP surface verified
via DRF `APIClient` in committed tests plus a throwaway repro suite (deleted
after the run).

Test runs: `DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test <labels>`
- `api` — 92 tests, all OK.
- `core.tests.PurgeResignedTests core.tests.OvertimeNotificationTests core.tests.LeaveDeficitTests` — 9 tests, all OK.

## Verified working (evidence)

1. **Payroll net is server-computed, client `net_pay` ignored** —
   `PayrollItemSerializer` marks `net_pay` read-only (`core/serializers.py:226-233`)
   and `_save_computed` writes `net_pay = base - deductions`
   (`core/views.py:671-685`). POST with `"net_pay": "999999.00"` returns
   `"900.00"` and persists `900.00`. Evidence: `api/tests.py:430-451`
   (`test_payroll_net_pay_is_server_computed`) — PASS.
2. **Payroll PATCH recomputes net** — patching `{"deductions": "50.00"}` on a
   `1000.00/900.00` line returns `"950.00"` (`core/views.py:692-693` falls back
   to instance `base_pay`). Evidence: `api/tests.py:414-428` — PASS.
3. **Duplicate payroll line → 409** — `unique_together (payroll_run, employee)`
   (`core/models.py:181-182`), auto-validator disabled
   (`core/serializers.py:231-233`), `IntegrityError` mapped to `Conflict409`
   (`core/views.py:684-685`). Evidence: `api/tests.py:396-412` — PASS.
4. **Payroll run/item create + audit signal** — `PayrollRun`/`PayrollItem`
   post_save audit rows (`core/signals.py:126-149`); frontend live-renders runs
   with line counts and summed `net_pay` from `GET /api/payroll-runs/` +
   `GET /api/payroll-items/` (`static/js/dashboard.js:1653-1693`). No test
   asserts the frontend sum; API side covered by 1–3.
5. **`ClaimStatus` validation + idempotent upsert** — `status` restricted to
   Pending/Approved/Rejected (`core/serializers.py:308-310`), blank `claim_id`
   rejected (`core/serializers.py:316-322`), POST returns 200 and
   `get_or_create` + conditional save keeps one row per `claim_id`
   (`core/views.py:759-775`). Evidence: `api/tests.py:713-748` (empty payload
   → 400, blank id → 400, unknown status → 400, idempotent upsert) — PASS.
6. **Expense-claim guards** — auth required (anon GET → 403),
   `amount` has `MinValueValidator(0.01)` (`core/models.py:197-201`,
   negative → 400), `employee` required (missing → 400). Evidence:
   `api/tests.py:750-776` — PASS.
7. **Messages bind sender to request user; default conversation key** —
   `sender_name` and `conversation_key` are read-only
   (`core/serializers.py:285-291`); `perform_create` forces
   `sender_name` from `request.user` and defaults `conversation_key` to
   `"general"` (`core/views.py:748-752`). Spoofed `sender_name: "Evil"` is
   replaced; missing key yields `"general"`. Evidence:
   `api/tests.py:695-711` — PASS. Attachment path: `attachment_url` built from
   request (`core/serializers.py:293-298`); text-or-attachment required
   (`core/serializers.py:300-305`). Frontend posts `FormData` with
   `conversation_key` and renders `attachment_url` (`static/js/dashboard.js:
   1180-1216, 1147-1173`).
8. **Notifications list + mark-read round trip** — `GET /api/notifications/`
   (`api/urls.py:180-184`, `core/views.py:788-790`) and
   `PATCH /api/notifications/<pk>/read/` (`api/urls.py:185-189`,
   `core/views.py:793-798`) return 200 with `is_read: true` persisted.
   Evidence: `api/tests.py:836-854` — PASS. Leave-decision signal creates a
   `kind="leave"` notification (`core/signals.py:164-181`); overtime approval
   creates `kind="payroll"` (`core/signals.py:204-214`); shift assignment
   creates `kind="shift"` (`core/signals.py:184-191`). Evidence:
   `api/tests.py:856-874`, `core/tests.py:91-135,281-327` — PASS.
9. **Purge dry-run counts without deleting; real run deletes + audits** —
   `--dry-run` prints `would purge …` and skips Supabase + delete
   (`core/management/commands/purge_resigned.py:31-33`); real run deletes the
   Supabase user first, writes an `EmployeeAuditLog`, then deletes the row
   (`purge_resigned.py:34-46`). `POST /api/purge-run/` (`core/views.py:801-830`,
   staff-only via `IsAdminUser`) parses the command output into
   `{dry_run, would_purge, purged, log}`. Evidence: `api/tests.py:916-965`
   (dry-run `would_purge: 1/purged: 0`, row kept; real run row gone + audit
   row), `core/tests.py:169-247` (only old resignations removed, failure keeps
   row, audit written) — PASS. Non-staff POST → 403 (`api/tests.py:910-914`);
   non-integer `days` → 400 (`api/tests.py:967-974`, `core/views.py:809-815`).
10. **Purge doubles as resign-time deauth retry** — resign (`DELETE
    /api/employees/<id>/`) sets `is_active=False` + `resigned_at`, attempts
    Supabase delete fail-open with a `deauthed=` flag in the audit row
    (`core/views.py:230-262`); a later purge retries the Supabase delete for
    the same user (`purge_resigned.py:36`). Supabase failure skips the row and
    keeps it (`purge_resigned.py:42-44`). Evidence: `core/tests.py:211-224`
    (`test_purge_failure_keeps_row`) — PASS; frontend surfaces
    `deauthed === false` as "purge will complete it"
    (`static/js/dashboard.js:553-554`).
11. **Conflicts endpoint names roster + leave** — `GET
    /api/shift-rosters/conflicts/?employee=<uuid>&date=<yyyy-mm-dd>`
    (`api/urls.py:110-114`, `core/views.py:520-545`) returns
    `{date, conflicts: [{roster, leave}]}` for Approved-leave overlaps, and
    400 when params are missing. Evidence: `api/tests.py:876-908` — PASS.
    Frontend decorates roster rows with a "leave clash" badge per hit
    (`static/js/dashboard.js:1640-1650`).

## Bugs found (repro)

All four reproduced with a throwaway `APIClient` suite (6 tests, all executed;
file deleted afterwards). In tests the original exception propagates through
the test client; in production each of B1–B2 is an unhandled exception → HTTP
500 (the custom handler only reshapes DRF responses —
`core/exception_handler.py:4-26` — and `Conflict409` is the only mapped domain
error, `core/exceptions.py:4-7`).

- **B1. `POST /api/purge-run/` with negative `days` → unhandled `CommandError`
  (500).** `int("-5")` passes (`core/views.py:809-815`), then `call_command`
  raises `CommandError("--days must be >= 0.")`
  (`core/management/commands/purge_resigned.py:26-27`) with no `try` around
  `call_command` (`core/views.py:818`). Repro: staff POST
  `{"days": -5, "dry_run": true}` → `CommandError` propagated out of the view.
  The management command itself rejects negatives correctly
  (`core/tests.py:226-230`); only the API wrapper misses it. Fix: validate
  `days >= 0` in the view (400) or catch `CommandError`.
- **B2. `GET /api/shift-rosters/conflicts/` with bad `employee` or `date` →
  unhandled Django `ValidationError` (500).** Filters pass raw params straight
  to the ORM (`core/views.py:529-535`). Repro: `?employee=xxx&date=2026-10-01`
  → `ValidationError: '"xxx" is not a valid UUID'`; valid UUID with
  `?date=not-a-date` → `ValidationError: invalid date format`. Only the
  missing-params case returns 400 (`core/views.py:524-528`). Fix: catch
  `ValidationError`/`ValueError` → 400.
- **B3. `POST /api/purge-run/` `dry_run` parsing is string-truthy.**
  `dry = bool(request.data.get("dry_run", True))` (`core/views.py:816`):
  `bool("false") is True`, so a form-encoded `dry_run=false` (or `"0"`)
  silently performs a **real purge**. JSON booleans (what the tests send) are
  unaffected. Fix: parse explicitly (`str(v).lower() in ("true","1",...)`
  or `is True` check). Severity: high if any client posts form data; latent
  for the current JSON frontend (which never calls this endpoint — see
  Unwired).
- **B4 (data-integrity gap, verified). `PATCH /api/notifications/<pk>/read/`
  and `GET /api/notifications/` are globally scoped.** Querysets are unfiltered
  (`core/views.py:788-798`); repro: user B lists notifications and sees user
  A's `kind="leave"` row (200, count 1). Any authenticated user can read and
  mark anyone's notifications read. No committed test covers scoping. Fix:
  filter by `request.user`'s employee (or restrict to staff) and 404/403 on
  foreign pks.
- **B5 (minor, code-evident). Three different conversation-key defaults.**
  Model default `"sarah"` (`core/models.py:224`), list default `"sarah"`
  (`core/views.py:745`), create default `"general"` (`core/views.py:751`).
  Net effect: a message created without a key lands in `"general"` but a bare
  `GET /api/messages/` reads `"sarah"` — the new message is invisible to the
  default listing. Committed tests pin the create side (`api/tests.py:708-711`)
  but nothing pins the read side. Fix: single constant for all three.
- **B6 (gap, verified). Negative `net_pay` accepted.** POST
  `base_pay 100.00 / deductions 200.00` → 201 (net `-100.00`). No
  `deductions <= base_pay` / non-negative guard in `_save_computed`
  (`core/views.py:671-685`) or the model (`core/models.py:173-182`). Whether
  negative net is ever legitimate is a product call; currently it is silently
  allowed. Related: nothing locks lines once `PayrollRun.is_processed=True` —
  lines can be added/edited on a processed run.

## Unwired/dead ends

(Checked by grepping every `apiFetch(`/`fetch(` call site in
`static/js/dashboard.js` — 28 hits — plus `static/js/`, `pages/dashboard.html`,
`pages/dashboard-preview.html`, `core/templates/core/index.html`.)

1. **`/api/expense-claims/` — implemented and tested, zero frontend callers.**
   No `expense-claims` string anywhere in `static/js/`, `pages/`, or templates.
   The visible Claims UI is static HTML with hardcoded rows
   (`pages/dashboard.html:2208-2420`, e.g. `id="status-CLM-2026-081"` at :2232)
   driven solely by `/api/claim-statuses/` (`static/js/dashboard.js:896-946`).
2. **`ExpenseClaim` and `ClaimStatus` are parallel, unlinked stores.** No FK,
   no lookup, no signal connects them: `ClaimStatus.claim_id` is a free
   `CharField(unique)` (`core/models.py:236-239`) keyed by the hardcoded DOM
   strings (`CLM-2026-08x`, `ADV-2026-01x` — the latter aren't even claims),
   while `ExpenseClaim` has its own UUID pk + own `status` field
   (`core/models.py:193-212`). Approving in the UI mutates `ClaimStatus` only;
   the `ExpenseClaim.status` row (the auditable record) never changes, and no
   `Notification`/audit is emitted for claim decisions. Any "claims are wired
   end-to-end" claim is false for the `ExpenseClaim` model.
3. **`/api/notifications/` + `/read/` — implemented and tested, zero frontend
   callers.** No `notifications` fetch in `static/js/` or templates; nothing
   polls them, no badge, no toast feed. Writers exist (signals, swap views),
   readers don't — notifications accumulate unread.
4. **`/api/purge-run/` — implemented and tested, zero frontend callers.** No
   `purge-run`/`purge` fetch in `static/js/` (only the deauth toast text at
   `dashboard.js:554`); retention runs are CLI/cron-only (`README.md:28-38`).
   Combined with B3, any future "Purge now" button must fix `dry_run` parsing
   first.
5. **No `/api/chat/` endpoint — and none is needed.** Chat is served by
   `/api/messages/` (`api/urls.py:164`); `dashboard.js` GETs
   `/api/messages/?conversation=<key>` (:1133) and POSTs `FormData` (:1198).
   "Chat API unwired" would be a misreport; the messages wiring is the chat
   wiring and it works (Verified 7).
6. **Payroll frontend is read-only by construction.** `loadPayrollView` only
   GETs runs + items and sums `net_pay` client-side (`dashboard.js:1653-1693`);
   there is no create/edit UI, so run creation, line entry, and the B6
   negative-net case are API-only paths. The live table additionally matches
   lines by `i.payroll_run === run.id` (:1674) — correct against the
   serializer's PK field (`core/serializers.py:229`).
7. **Conflicts badge is advisory-only.** The endpoint result only decorates a
   roster cell (`dashboard.js:1642-1649`); nothing blocks creating a roster
   over an approved leave (roster overlap guard covers roster-vs-roster only,
   `core/serializers.py:165-177`). Pending leaves are ignored by design
   (`status="Approved"` filter, `core/views.py:530-535`) — fine, but worth
   stating so "conflict prevention" isn't over-claimed.
