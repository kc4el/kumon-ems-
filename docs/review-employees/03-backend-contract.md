# Employee backend contract

Scope: `api/urls.py:59-60`, `core/views.py:115-237` (`EmployeeListCreateView`, `EmployeeDetailView`), `core/serializers.py:32-45` (`EmployeeSerializer`), `core/models.py:27-42` (`Employee`), `api/tests.py` + `core/tests.py` employee cases. Commit point: branch `chore/standard-format` as read.

## Exposed vs hidden fields

Model (`core/models.py:27-42`) fields: `id` (UUID PK, `editable=False`), `first_name`, `last_name`, `email` (`unique=True`), `role` (`blank/null`), `department` (FK `SET_NULL`, `null/blank`), `date_hired` (`auto_now_add=True`), `is_active` (`default=True`), `resigned_at` (`null/blank`).

Serializer (`core/serializers.py:32-45`) exposes: `id`, `first_name`, `last_name`, `email`, `role`, `department`, `date_hired`, `is_active`. `read_only_fields = ["id", "date_hired"]`.

Hidden from the API surface:

- `resigned_at` is model-writable but **not a serializer field**. It is never accepted on POST/PUT/PATCH, and never rendered in list/detail GET bodies. It is only surfaced indirectly: `EmployeeDetailView.destroy` (`core/views.py:213-237`) returns `{"id", "is_active": False, "resigned_at", "purge_on"}` with HTTP 200. `purge_on` is a computed `resigned_at + 30d` response-only value, not a model field.
- No other model field is hidden: the model has no `created_at`/`updated_at`, no password hash, no staff flags — there is nothing else to leak or hide.

Editable via API (all writable unless read-only above): `first_name`, `last_name`, `email`, `role`, `department` (PK write), `is_active`. Consequences at field level:

- `email` is writable on PUT/PATCH with **no uniqueness re-check in the view/serializer** (the 409 `email__iexact` guard exists only in `EmployeeListCreateView.post`, `core/views.py:150-154`). An update to a colliding email falls through to the DB unique constraint → 500-path via `EXCEPTION_HANDLER`, not the 409 the create path returns. No test covers PATCH-email collision.
- `is_active` is directly writable on PUT/PATCH by any authenticated caller. Setting `is_active=false` via PATCH writes the flag **without** setting `resigned_at` and without writing the `resigned ... purge on ...` audit row (the signal in `core/signals.py:62-63` only skips the generic log when `update_fields == {"is_active","resigned_at"}`; a PATCH touching only `is_active` logs a generic "updated" row, and a PATCH touching `is_active` + anything else also logs generic). Only the DELETE path sets `resigned_at` and the distinct audit row.
- `is_active` can be flipped back to `true` via PATCH/PUT (reactivation) with no guard and no audit distinction; `resigned_at` stays stale (non-null) because it is not exposed/editable to clear.
- `department` accepts any department PK (including cross-assigning to a department the caller does not manage); no validation beyond FK existence.
- `role` is a free-text `CharField`, no choices — any string (including privilege-sounding values) persists; it carries no permission semantics server-side.
- `date_hired` is read-only and `auto_now_add`, so client-supplied values are silently dropped (covered by `api/tests.py:371-390`: POST with `date_hired=2000-01-01` returns 201 with today's date).
- `password` in `EmployeeListCreateView.post` (`core/views.py:134-181`) is a **write-only phantom field**: read from `request.data`, used to create the Django `User`, never part of the serializer or the `Employee` model. Posting without it still creates the Supabase auth user + employee row (no password set anywhere).

Representation gaps the frontend must work around:

- `department` serializes as a raw PK (no `department_name` nesting). `dashboard.js:1475` reads `emp.department_name` (always `''`) for the `data-dept` filter attribute — dead attribute, not a backend bug but a contract mismatch to note.
- List ordering is fixed server-side (`EmployeeListCreateView.queryset ... .order_by("last_name","first_name")`, `core/views.py:116`; covered by `api/tests.py:61-71`). No client ordering override exists.

## Auth/scope gaps (mobile lens)

Current posture: `kumon_ems/settings.py:177-192` sets `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` (Session + Token auth). The only employee-specific override is `EmployeeListCreateView.get_permissions` (`core/views.py:119-124`): POST is `AllowAny`, everything else falls through to `IsAuthenticated`.

Per-endpoint gaps, assuming a future mobile app where each employee authenticates as themselves:

1. `POST /api/employees/` — **anonymous self-service signup** (`AllowAny`). Creates a Supabase auth user + `Employee` row (+ Django `User` iff `password` supplied) with no CAPTCHA, approval, staff check, or rate-limit beyond global anon throttle 100/day. Any device can mint identities; `email__iexact` 409 check lets an attacker enumerate registered emails. Required for current logged-out onboarding; unsafe as a mobile registration endpoint without an invite/approval gate.
2. `GET /api/employees/` — any authenticated user (including a freshly self-signed-up one) lists **all** employees with PII (`first_name`, `last_name`, `email`, `role`, `department`, `is_active`). No `get_queryset` scoping, no `IsAdminUser`, no `?employee=` self-filter — full directory dump per call. Mobile lens: every employee sees every other employee's contact record.
3. `GET /api/employees/<uuid>/` — same: any authenticated caller retrieves any employee by UUID. No ownership check (`request.user` ↔ employee link does not exist server-side; `Employee` has no `user` FK at all). Mobile lens: IDOR by design — no notion of "my profile".
4. `PUT/PATCH /api/employees/<uuid>/` — any authenticated caller can edit **any** employee's `first_name/last_name/email/role/department/is_active`. Mass-assignment is bounded (serializer field list), but there is no owner-or-admin gate, so one mobile user can rename, reassign, deactivate, or email-squat another employee. `is_active=false` via PATCH is a silent deactivation that bypasses the resign flow (see above).
5. `DELETE /api/employees/<uuid>/` — any authenticated caller can soft-delete (deactivate) any employee. No `IsAdminUser` (contrast `PurgeRunView`, `core/views.py:776-777`, which is admin-only). Idempotent (re-DELETE keeps 200, `core/views.py:215-218`), but the audit write is guarded by `action__icontains="resigned"` existence (`core/views.py:222-224`), so repeat deletes do not duplicate the row.
6. No `Employee` ↔ `auth.User` linkage server-side beyond coincidental email match. Token auth identifies a `User`; nothing maps that `User` to an `Employee` row, so owner-scoping cannot be expressed today even if a mobile client wanted `GET /me`. Any per-user scoping first requires a `user` FK (or equivalent) on `Employee`.
7. `GET /api/dashboard-summary/` is `AllowAny` (`core/views.py:73`) and counts `Employee`/`LeaveRequest`/`Attendance` rows. Counts-only, but a mobile client on a public network gets org headcount/activity without auth. Intentional per comment (B10); flag only.

What is **not** a gap: anonymous GET is denied (403, `api/tests.py:30-38`); token issuance requires valid credentials. Detail-view auth inherits the default — the problem is authorization scope, not missing authentication.

## Unused backend capability

Capability the backend already provides that the desktop frontend does not consume (employee endpoints only):

1. **Pagination (global `PageNumberPagination`, `PAGE_SIZE 10`, `settings.py:185-186`).** Every list (including `/api/employees/`) returns `{"count","next","previous","results"}` (`api/tests.py:53-59` asserts the envelope). The directory loader (`dashboard.js:1460-1467`) reads `results` but never follows `next`, never renders page controls. It fetches only page 1 — employees beyond row 10 are invisible in the directory view.
2. **`?page_size=50` is a no-op the frontend relies on.** `dashboard.js:537,1509` requests `/api/employees/?page_size=50` expecting 50 rows. `PAGE_SIZE_PARAM` is not configured, so DRF ignores the param and still returns 10/page. Three call sites (`:537` offboard lookup, `:1509` name cache, plus `:1460` bare) silently operate on a truncated set: offboarding lookup by email misses anyone past page 1; `liveEmployeeNameCache` maps only the first 10 ids.
3. **Fixed server ordering** (`last_name, first_name`). The frontend applies no ordering of its own and offers no sort control; it inherits backend order wherever it renders `results` in arrival order (`:1469`, `:1514`).
4. **No search/filter/ordering backends anywhere.** Confirmed: no `filter_backends`, `SearchFilter`, `OrderingFilter`, `filterset_fields`, `search_fields`, or `ordering_fields` on either employee view; the sole `get_queryset` override in the codebase is `MessageListCreateView` (`core/views.py:719-721`). Employee-side filtering (`?search=`, `?department=`, `?is_active=`) does not exist — the README claim ("supports search/filtering") is satisfied client-side only: `filterDirectory()` filters already-fetched DOM cards. At 10 rows/page this hides most of the directory from search.
5. **Soft-delete response fields.** `destroy` returns `resigned_at` + computed `purge_on` (`core/views.py:229-236`), but no frontend path reads them: the offboard handler (`dashboard.js:546-548`) checks only `delRes.ok` and toasts a static message. The "exit clearance / purge date" data the API computes is discarded.
6. **Inactive-row visibility.** List queryset is unfiltered (`Employee.objects.all()`), so resigned (`is_active=false`) rows are included in page 1 results. The frontend does render an Inactive badge (`dashboard.js:1488-1489`) — but because pagination truncates, actives pushed to page 2+ never render while inactives on page 1 do.
7. **Audit trail on resign.** `destroy` writes exactly one `EmployeeAuditLog` row (`resigned ... purge on ...`), and the signal suppresses the duplicate generic row (`signals.py:59-63`). The audit-logs list endpoint exposes it, but the employee UI never surfaces per-employee audit state.

Soft-delete consistency notes (all verified in code + tests):

- DELETE never hard-deletes: both `perform_destroy` (`core/views.py:208-211`) and the overriding `destroy` (`core/views.py:213-237`) set `is_active=false` + `resigned_at=today` (`timezone.localdate`, Asia/Singapore per `settings.py:140`). `perform_destroy` is dead code — `destroy` fully overrides it (duplicated logic, same `update_fields`). Test `api/tests.py:408-424` asserts row survives with `is_active=false`, `resigned_at=today`, response 200 (not 204) containing `id/is_active/resigned_at/purge_on`.
- List/detail do **not** exclude resigned rows; `dashboard-summary` counts `total = all`, `active = is_active=true` (`core/views.py:77-78`). Purge (`purge_resigned` mgmt command, `core/tests.py:174-246`) hard-deletes only `is_active=false` + `resigned_at older than N days`; `PurgeRunView` defaults `dry_run=true`, admin-only.

## Suggested fixes (narrowest first)

Ordered by smallest diff; admin-only desktop scope preserved, mobile lens flagged, nothing applied (read-only task).

1. **Stop over-fetching on a lie: drop `?page_size=50` or honor it.** Either remove the param from the three frontend call sites (accept 10/page) or set `PAGE_SIZE_PARAM = "page_size"` (+ sane `MAX_PAGE_SIZE`, e.g. 100) in `REST_FRAMEWORK`. One-line settings change; un-breaks offboard lookup and the name cache without touching views. Risk if honored: clients can request large pages — cap with `MAX_PAGE_SIZE`.
2. **Add server-side employee search + `is_active`/`department` filters.** Narrowest: `filter_backends = [SearchFilter, OrderingFilter]` + `search_fields = ["first_name","last_name","email"]`, `ordering_fields = ["last_name","first_name","date_hired"]` on `EmployeeListCreateView`, and an explicit `is_active`/`department` query-param filter in `get_queryset`. Lets the directory and offboard lookup stop depending on full-list fetches; prerequisite for any mobile directory.
3. **Paginate or follow `next` in the three employee fetchers.** Until (2) lands, loop `next` links in `loadEmployeeDirectory`/`liveEmployeeNames`/offboard lookup, or switch offboard lookup to a server filter from (2). Frontend-only, no API change.
4. **Close the PATCH-deactivation bypass: make `is_active` read-only on update, or route it through the resign flow.** Narrowest backend fix: add `is_active` to `read_only_fields` for PUT/PATCH (keep DELETE as the sole deactivation path), or override `perform_update` to set `resigned_at` + audit row when `is_active` flips false. Fixes silent deactivation + stale `resigned_at` + missing audit without a schema change.
5. **Re-check email uniqueness on update.** Mirror the create-path `email__iexact` 409 (or a serializer `UniqueValidator` case-insensitive) in `EmployeeDetailView.perform_update`. Prevents PATCH-email collisions from surfacing as 500s and blocks email-squat renames.
6. **Gate write endpoints for the mobile future (do not apply under current admin-only scope without product sign-off).** Minimum: require `IsAdminUser` (or a manager role) on POST/PUT/PATCH/DELETE employee; add an `Employee.user` FK and a `/employees/me/` (or `?mine=`) owner-scoped read so a mobile client can fetch exactly its own profile. This is the actual mobile blocker — items 1-5 are correctness/hygiene, this one is architectural. Note POST-`AllowAny` must stay until onboarding gains an invite/approval flow; gating it now breaks logged-out signup.
7. **Dedupe `perform_destroy` vs `destroy`.** Delete the dead `perform_destroy` (`core/views.py:208-211`); keep `destroy` as the single soft-delete path. Zero behavior change, removes a future divergence trap.
8. **Expose `resigned_at` read-only (optional, low value).** Adding it to `fields` + `read_only_fields` lets clients render tenure/offboard state without DELETE-response scraping. Cheap; skip if the desktop UI will not use it — otherwise `purge_on` stays the only visibility into the field and only at delete time.
