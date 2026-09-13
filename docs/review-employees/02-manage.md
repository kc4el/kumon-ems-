# 02 — Employee MANAGE view (promote / transfer / onboard / offboard)

Scope: `core/templates/core/index.html` lines 986–1382 (MANAGE view) + onboarding
wizard modal (~3802–3938+), `static/js/dashboard.js` `setPtMode` (~491),
`handleOffboardingSubmit` (~528), `handleOnboarding` (~580), `showToast` (~823),
`loadEmployeeDirectory` (~1457); `core/views.py` `EmployeeListCreateView` (115–201),
`EmployeeDetailView` (204–237); `core/serializers.py` `EmployeeSerializer` (32–45);
`core/signals.py` `log_employee_action` (51–67). Branch `chore/standard-format`.
Desktop web is ADMIN-ONLY (standing scope).

## Wired end-to-end

### 1. Create (Onboard New Employee) — ✅ WIRED
Trace:
`Onboard New Employee` button (`index.html:1372`, `onclick="openOnboardingModal()"`)
→ modal `#onboardingModal` (`:3805`, form `onsubmit="handleOnboarding(event)"` at `:3819`)
→ `handleOnboarding` (`dashboard.js:580`) reads **only** the first text input
(full name → split into `first_name`/`last_name`) and the first email input,
`POST /api/employees/` with `{first_name, last_name, email}`
→ `EmployeeListCreateView.post` (`views.py:126`): 400 no-email (`:129–133`),
DRF validation → 400 `{error}` (`:145–149`), duplicate-email pre-check
(`email__iexact`) → **409** (`:150–154`), Supabase Auth `create_user` + DB save
in `transaction.atomic()` with auth-rollback on DB failure (`:155–182`),
`IntegrityError` race → 409 (`:183–188`), upstream failure → 502 (`:189–201`)
→ serializer `EmployeeSerializer` (no custom validators; `id`/`date_hired` read-only)
→ DB `Employee` row (id = Supabase auth UUID)
→ signal `log_employee_action` writes `"Employee profile created …"` audit row
(`signals.py:53–57`)
→ JS: `!res.ok` → `showToast(err)`; success → success toast +
`closeOnboardingModal()` + `form.reset()` + **`loadEmployeeDirectory()` refresh**
(`dashboard.js:595–613`).

Caveats (not unwired, but lossy): the wizard's Department / Job Role / Assigned
Manager / Start Date / IT-asset checkboxes (`:3832–3938+`) are **never read** by
`handleOnboarding` — only name+email are POSTed, so `role`/`department` are always
NULL on create. The 409 duplicate-email toast works (backend returns
`{error: string}`) but renders in the same style as success because `showToast`
ignores its second arg (see Validation gaps).

### 2. Remove / Offboard (incl. resignation) — ✅ WIRED (with gaps)
There is no separate resignation endpoint; the offboarding wizard **is** the
resignation flow, via the generic soft-delete.
Trace:
offboard form `onsubmit="handleOffboardingSubmit(event)"` (`index.html:1143`)
→ `handleOffboardingSubmit` (`dashboard.js:528`): requires corporate email
(missing → error toast `:533`), `GET /api/employees/?page_size=50`, case-insensitive
email match (no match → error toast `:543`), `DELETE /api/employees/<id>/`
→ `EmployeeDetailView.destroy` (`views.py:213`): sets `is_active=False`,
`resigned_at=today`, writes one distinct audit row
`"resigned <date>, purge on <date+30>"` (idempotent via `action__icontains`
check, `:222–228`); the `post_save` signal skips its generic "updated" row for
exactly this `update_fields` set (`signals.py:62–63`), so **exactly one audit row**
→ JS success toast (`:548`) + `form.reset()`.
(`perform_destroy` at `:208–211` is dead code — `destroy()` is overridden and
never calls it; same logic duplicated.)

Gaps: **no post-action refresh** (no `loadEmployeeDirectory()` call, unlike
onboarding); **no Supabase Auth user deactivation** on resign (server-side gap —
resigned user keeps auth access until the manual `purge_resigned` hard-delete);
lookup is capped at `page_size=50` so emails beyond the first page report
"No employee found"; DELETE failure (incl. 404) collapses to one generic toast
(`:547–551`, `!delRes.ok → throw`); re-DELETE of an already-inactive employee
succeeds silently with the same success toast (idempotent but indistinguishable).

## Toast-only / dead controls

`showToast` is defined `function showToast(message)` (`dashboard.js:823`) — a
**single parameter**, so every `'error'` second argument passed at call sites is
silently dropped (no error styling anywhere in this view).

| # | Control (index.html) | Call site | Classification |
|---|---|---|---|
| 1 | `Record Promotion` button (`:1079–1080`, `onclick="showToast('Promotion recorded successfully!')"`) | inline | **Toast-only / dead.** No `fetch`, no endpoint, no DB write, no audit row. `setPtMode` (`:491–524`) is a pure CSS container toggle. There is **no promote API** — `role`/pay-grade/effective-date/rationale inputs have no `id`/`name` and are never read by any JS. |
| 2 | `Record Transfer` button (`:1135–1136`, `onclick="showToast('Transfer recorded successfully!')"`) | inline | **Toast-only / dead.** Same as above; no transfer endpoint exists (`department`/location/work-mode/date/reason never leave the DOM). |
| 3 | Promote/Transfer `Cancel` buttons (`:1078`, `:1134`, no `onclick`) | — | **Dead.** No handler at all; button does nothing. |
| 4 | Offboard `Cancel` (`:1363`, `onclick="setPtMode('promote')"`) | `setPtMode` | Cosmetic only — switches tab, discards nothing explicitly (native form state persists). |
| 5–8 | Four `Upload File` buttons, Step 3 (`:1292–1293`, `:1304–1305`, `:1316–1317`, `:1328–1329`, `onclick="showToast('Upload dialog opened for …')"` ) | inline | **Toast-only / dead.** No `<input type=file>`, no upload endpoint; resignation letter / exit-interview / confidentiality / final-pay docs cannot be attached. |
| 9 | `✕` file-remove (`:1347–1348`, dims parent + `showToast('File removed')`) | inline | Cosmetic DOM effect only; the `Samantha Vance - Exit Clearance Agreement.pdf` chip is static markup, not a real attachment. |
| 10 | IT-clearance / HR-cleared badges (`:1276–1282`, `:1351–1357`) | — | Static markup; asset checkboxes and clearance state are never validated or persisted. |

Out of scope but adjacent (same file, Grievance tab): grievance submit
(`handleGrievanceSubmit`, `:618–622`) is accepted posture toast-only per brief —
not re-flagged beyond this pointer.

## Validation gaps

1. **Promote/transfer: zero validation** — there is no client or server path, so
   required-ness (new role, pay grade, effective date, rationale / target dept,
   location, reason) is unenforceable. Duplicated "success" toasts actively
   mislead: an admin believes a promotion/transfer was recorded when nothing
   happened.
2. **Onboarding drops most fields silently.** Department, Job Role, Manager,
   Start Date, IT assets are collected in the UI but never POSTed; no warning
   tells the admin they were discarded. `role`/`department` end up NULL and must
   be fixed via a separate PATCH (which itself has no UI in this view).
3. **Onboarding name split is naive.** `parts[0]` / `parts.slice(1)` — a single
   name yields `last_name: ''` → backend 400 (`last_name` has no `blank=True`);
   the 400 `exc.detail` for field errors is a **dict, not a string**, so
   `typeof data.error === 'string'` fails and the user gets the generic
   "Check the form" toast with no field indicated. Blank email → caught
   client-side only by `required`; whitespace-only name passes JS and 400s.
4. **Duplicate handling: email yes, ID n/a.** Duplicate *email* → proper 409
   pre-check + race guard (`views.py:150–154, 183–188`) surfaced via toast.
   Duplicate *ID* cannot occur from this UI — `id` is read-only in the serializer
   and server-generated from the Supabase auth UUID. No EMP-code/employee-number
   concept exists, so "duplicate-ID handling" has no surface here.
5. **400/409 toasts exist for create, undifferentiated.** `handleOnboarding`
   shows `data.error` for any non-OK (400/409/502 all render the same toast;
   502 upstream-fail message is user-friendly). `showToast(msg, 'error')` type
   args are dropped (single-param def), so error toasts look identical to success.
6. **Offboard validation is email-only.** Name/department/role/last-day/reason/
   notice-period/asset-checkbox inputs are display-only; only the email field is
   read. `page_size=50` lookup cap (above) is a false-negative source. No
   confirmation step before irreversible-feeling "Finalize Offboarding".
7. **No auth/actor on audit rows.** Create/resign audit rows record no actor
   (consistent with repo-wide posture; `EmployeeAuditLog` endpoint is read-only
   at `api/urls.py:160`, good) — noted for completeness, not as a new finding.

## Suggested fixes (narrowest first)

1. **Stop lying on promote/transfer (1-line-ish).** Replace the two inline
   `showToast('…recorded successfully!')` with a honest placeholder
   (`'Promotion workflow is not yet connected.'`) or `disabled` buttons until a
   backend exists. Cheapest trust fix; zero API work.
2. **Fix `showToast` signature** (`dashboard.js:823`): accept and apply the
   `type` argument (`toast.classList.add(type)` + error styling). One-line fix
   that upgrades every existing `'error'` call site in the view at once.
3. **POST the fields onboarding already collects.** Extend `handleOnboarding` to
   read Job Role → `role`, Department → resolve `department` id (needs a
   `GET /api/departments/` lookup or accept names server-side); add
   `loadEmployeeDirectory()`-style refresh already present. Backend already
   accepts both fields via `EmployeeSerializer`.
4. **Refresh after offboard.** Add `loadEmployeeDirectory()` (and clear any
   cached `liveEmployeeNameCache`) on successful DELETE — mirrors the create
   path; one line.
5. **Raise offboard lookup cap / resolve exactly.** Use `?page_size=200` (or a
   dedicated `?email=` filter / `retrieve-by-email` endpoint) and surface
   non-OK DELETE status distinctly (404 vs 500) instead of one generic toast.
6. **Wire promote/transfer for real (larger).** Decide the data model first
   (mutate `Employee.role`/`department` via `PATCH /api/employees/<id>/` with
   effective-date/rationale → audit row, vs. a history table). Until then, fix #1
   so the UI doesn't promise what the API can't do. Note `PATCH` on
   `EmployeeDetailView` currently fires the generic "profile updated" audit row
   — acceptable for promote/transfer but rationale text would be lost without a
   dedicated action/endpoint.
7. **Deactivate the Supabase auth user on resign** (`EmployeeDetailView.destroy`):
   currently only `purge_resigned` (manual cron) deletes the auth user, leaving a
   resigned employee's credentials valid for up to 30 days. (Server-side; listed
   here because the MANAGE view's "Revoke access" checkboxes imply it happens.)
