# Employee reviews — COMPILED top gaps

## Honesty header (read first)

- **Scope: desktop web ADMIN-ONLY.** All items below assume a trusted admin on desktop
  web. Mobile-lens authorization notes from review 03 are consolidated into a single
  P1 blocker item; per-endpoint IDOR details are otherwise out of scope.
- **Static-vs-live is disclosed posture.** Demo cards, hardcoded filter lists, and
  static profile bodies are accepted demo stand-ins where the LIVE badge + toast
  disclose state — not re-flagged except where a live path actively disagrees
  (status words, dept filter, pagination truncation).
- **Grievance non-disclosure stands.** `handleGrievanceSubmit` toast-only is accepted
  posture per brief — not listed below (pointer in review 02 only).
- **Demo badges / toast-only grievance / disclosed static-vs-live are dropped.**
  Probation/On-Leave static badges, grievance toast-only, and plain static demo
  bodies are not gaps here.
- Cap: 15 items max, severity forced. Duplicates merged; credit kept per item
  as (01)/(02)/(03).

## P0 — broken promise (UI claims it, nothing happens / security lie)

### 1. Record Promotion / Record Transfer toast "success" with zero write — (02)
- Surface: MANAGE view Promote/Transfer tabs.
- Repro: fill promotion form → click `Record Promotion` → success toast, but no
  fetch, no endpoint, no DB/audit write.
- Fix: replace inline `showToast('…recorded successfully!')` with honest
  placeholder (`'Promotion workflow is not yet connected.'`) or `disabled` buttons.
- Source: `core/templates/core/index.html:1079-1080,1135-1136`

### 2. Onboarding collects Department/Role/Manager/Start Date/IT assets then discards them — (02)
- Surface: Onboard New Employee wizard modal.
- Repro: fill Department + Job Role → submit → `POST /api/employees/` body holds
  only `{first_name, last_name, email}`; `role`/`department` land NULL.
- Fix: extend `handleOnboarding` to read Job Role → `role` and Department →
  `department` id (via `GET /api/departments/` lookup); warn until wired.
- Source: `static/js/dashboard.js:580-613`; `core/templates/core/index.html:3832-3938`

### 3. Live dept filter dead: frontend reads `emp.department_name`, API sends PK — (03, also 01)
- Surface: directory `#deptFilter` on live rows.
- Repro: load directory live → select any department → live cards never match
  because `data-dept` is always `''` (`department_name` is undefined; serializer
  emits raw `department` PK).
- Fix: read `emp.department` (resolve PK→name via departments fetch) or nest
  `department_name` in the serializer.
- Source: `static/js/dashboard.js:1475`; `core/serializers.py:32-45`

### 4. Status badge words disagree with status filter; Probation unproducible — (01)
- Surface: directory badges vs `#statusFilter`.
- Repro: go live → badges read `Active/Inactive` while `data-status`/filter use
  `Present Today/On Leave/Probation`; select `Probation` → zero live rows ever.
- Fix: render badge text from the same `Present Today / On Leave` strings written
  to `data-status` (`dashboard.js:1477-1489`).
- Source: `static/js/dashboard.js:1477-1489`; `core/templates/core/index.html:415-420`

### 5. Directory + offboard lookup silently truncated: page 1 only, `?page_size=50` ignored — (03, also 01, 02)
- Surface: roster list, offboard email lookup, `liveEmployeeNameCache`.
- Repro: with >10 employees, `loadEmployeeDirectory` fetches `/api/employees`
  once (no `next`); `?page_size=50` is a no-op (`PAGE_SIZE_PARAM` unset) → rows
  past 10 invisible; offboard lookup reports "No employee found" for them.
- Fix: set `PAGE_SIZE_PARAM = "page_size"` + `MAX_PAGE_SIZE` (e.g. 100) in
  `REST_FRAMEWORK`, or follow `next` links in the three fetchers.
- Source: `static/js/dashboard.js:1460,537,1509`; `kumon_ems/settings.py:185-186`

### 6. `View Full Profile` / `Message on Slack` buttons dead — (01)
- Surface: all 6 demo profile cards.
- Repro: click either button → nothing (no `onclick`, no id, no handler in
  `dashboard.js`); live cards omit both entirely.
- Fix: bind to a profile modal / `mailto:` link, or delete from markup.
- Source: `core/templates/core/index.html:510-511,603-604,695-696,788-789,880-881,972-973`

### 7. Live cards summary-only: accordion expands to nothing — (01)
- Surface: live-rendered roster rows.
- Repro: load directory live → click a row → `.open` toggles but no
  `.acc-expanded-body` exists, so nothing reveals.
- Fix: include `.acc-expanded-body` with email/department in `card.innerHTML`.
- Source: `static/js/dashboard.js:1481-1490`

### 8. Resigned employee keeps auth access until manual purge — (02)
- Surface: offboard flow ("Revoke access" checkboxes imply revocation).
- Repro: offboard someone → `DELETE` sets `is_active=False` but never touches the
  Supabase auth user → credentials valid up to ~30 days until `purge_resigned`.
- Fix: deactivate the Supabase auth user inside `EmployeeDetailView.destroy`.
- Source: `core/views.py:213-237`

## P1 — missing expected HR function

### 9. `showToast` drops its `type` arg: errors look identical to success — (02)
- Surface: every error toast in MANAGE (400/409/502, offboard failures).
- Repro: trigger duplicate-email 409 → toast text correct, styling identical to
  success (`showToast(message)` takes one param; all `'error'` args dropped).
- Fix: accept and apply `type` (`toast.classList.add(type)` + error CSS).
- Source: `static/js/dashboard.js:823`

### 10. No directory search; no server search/filter — (01, 03)
- Surface: directory toolbar + `/api/employees/` query surface.
- Repro: try to find someone by name/email → no input exists; `?search=` /
  `?department=` / `?is_active=` all ignored (no filter backends; README claim is
  client-side DOM filtering of ≤10 fetched rows).
- Fix: add name/email input extending `filterDirectory`, plus `SearchFilter` +
  `search_fields = ["first_name","last_name","email"]` and `is_active`/`department`
  params on `EmployeeListCreateView`.
- Source: `core/templates/core/index.html:353-420`; `core/views.py:115-124`

### 11. Offboard: no roster refresh, generic errors, no confirm — (02)
- Surface: offboard wizard post-submit.
- Repro: offboard by email → success toast but roster still shows them
  (no `loadEmployeeDirectory()` call, unlike onboarding); 404 vs 500 collapse to
  one generic toast; no confirmation before finalize.
- Fix: call `loadEmployeeDirectory()` (+ clear name cache) on success; surface
  non-OK status distinctly; add confirm step.
- Source: `static/js/dashboard.js:528-551`

### 12. Onboarding validation: naive name split + dict-error swallowed — (02)
- Surface: onboarding form error paths.
- Repro: submit single-word name → `last_name: ''` → backend 400, but 400
  `exc.detail` is a dict so `typeof data.error === 'string'` fails → generic
  "Check the form" toast naming no field.
- Fix: require two name parts client-side (or separate fields); render dict field
  errors per-field.
- Source: `static/js/dashboard.js:580-613`; `core/views.py:145-149`

### 13. PATCH email to a colliding address → 500, not 409 — (03)
- Surface: `PUT/PATCH /api/employees/<uuid>/`.
- Repro: PATCH employee A's email to employee B's → DB unique constraint fires on
  the 500-path (the `email__iexact` 409 guard exists only on create).
- Fix: mirror the create-path `email__iexact` 409 (or case-insensitive
  `UniqueValidator`) in `perform_update`.
- Source: `core/views.py:150-154,204-237`

### 14. Exit-document upload buttons promise what doesn't exist — (02)
- Surface: offboard Step 3 (resignation letter / exit-interview / confidentiality /
  final-pay `Upload File` ×4 + file-remove chip).
- Repro: click any `Upload File` → toast only; no `<input type=file>`, no endpoint;
  the `Samantha Vance` chip + remove are static-markup cosmetics.
- Fix: honest placeholder/disabled state until a real attachment endpoint exists.
- Source: `core/templates/core/index.html:1292-1348`

## P2 — polish

### 15. Roster has no loading / empty / inline-error states — (01)
- Surface: `#employeeRosterList` fetch lifecycle.
- Repro: throttle network → no spinner; zero rows → blank list; pre-paint failure
  → only a toast, no in-DOM message (attendance view has all three).
- Fix: mirror attendance (`Loading…` on entry, `No employees…` on zero, inline
  error row in catch).
- Source: `static/js/dashboard.js:1457-1500` (cf. `:1530,1539-1540`)

## Deliberately dropped (over the cap / accepted posture)

- Hardcoded filter option lists drifting from API values (01) — real but weaker
  than item 3, which already covers live-filter breakage.
- PATCH/PUT/DELETE/List any-employee + anonymous-POST enumeration with no
  `Employee.user` linkage (03) — the actual mobile architectural blocker; under
  the current ADMIN-ONLY desktop scope it is noted here, not ranked, per 03's own
  "do not apply without product sign-off".
- `is_active` PATCH-reactivation leaving stale `resigned_at` (03) — folded toward
  item 8's resign-flow fix; needs `resigned_at` exposure or update guard.
- Dead `perform_destroy` duplication (03), dead Cancel buttons (02),
  `mailto:`/`tel:` + avatar/org-chart/export absences (01), `purge_on` computed
  value discarded by the offboard handler (03), `AllowAny` dashboard-summary
  counts (03, intentional per B10).
