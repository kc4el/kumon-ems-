# Review round 5 — COMPILED (top 20, duplicates merged)

## Honesty header

- **What this is:** a merge of all 8 files in `docs/review-round5/`
  (`01-auth-sessions.md` through `08-security-mobile.md`) on branch
  `chore/standard-format` (@ `64827c5`). No re-testing, no code changes.
- **What was NOT done:** no test runs, no dev server, no browser checks, no
  secret rotation, no tracked-file edits. Verification claims below are the
  source files' own stated evidence, not re-verified here.
- **Standing scope:** desktop ADMIN-ONLY. Mobile blockers are out of scope
  (dropped, see below).
- **Accepted posture (not re-flagged):** demo badges, grievance
  non-disclosure, disclosed static-vs-live fallbacks with honest toasts.
- **Secrets rotation is the human's job:** live secrets in git history
  (`08` V4) is noted, not tasked — see Deliberately-dropped.
- **Ranking:** CRITICAL = authz/auth bypass or destructive; HIGH = data
  integrity or brute-force; MED = 500s, wrong renders, low-severity integrity.
  Cap: 20 items. Duplicates merged; every item credits its source file(s).

## Findings

### CRITICAL

1. **No owner scoping (IDOR) on all detail endpoints** — surface: every
   `RetrieveUpdateDestroy` (`employees`, `leaves`, `payroll`, `notifications`,
   …). Repro: as any login, `PATCH /api/employees/<other-uuid>/` → 200.
   Fix: add `get_queryset` owner filter / object permission per view (needs a
   `User↔Employee` link first). Source: `08-security-mobile.md` V1 (absorbs
   `05-payroll-claims-purge.md` B4 notifications scoping).
2. **No role gates — any login can approve/resign anyone** — surface:
   corrections, swaps, overtime, leave, payroll, `DELETE /api/employees/`.
   Repro: as non-admin, approve a swap / resign another employee → 200.
   Fix: require `IsAdminUser` (or HR role) on approve/reject/payroll/resign
   mutations. Source: `08-security-mobile.md` V2.
3. **Resigned staff keep Django/token/session access** — surface: resign +
   `auth-token/` + session. Repro: token A → resign → `GET /api/employees/`
   with Token A → still 200. Fix: on resign delete `User` row(s) +
   `Token.objects.filter(user=…)` + flush sessions (suspend locally even when
   Supabase delete fails open). Source: `08-security-mobile.md` V3 (merges
   `01-auth-sessions.md` bugs 2, 5).

### HIGH

4. **`POST /api/purge-run/` `dry_run` string-truthy → accidental real purge** —
   surface: `PurgeRunView`. Repro: staff POST `{"days": 30, "dry_run": "false"}`
   form-encoded → real purge (`bool("false") is True`). Fix: parse explicitly
   (`str(v).lower() in ("true","1",…)`). Source: `05-payroll-claims-purge.md` B3.
5. **Credential endpoints brute-forceable (login unthrottled)** — surface:
   `session-login/` (`throttle_classes = []`) + `auth-token/` (DRF default
   `()`). Repro: loop bad-password POSTs → never 429. Fix: scoped burst
   throttle (e.g. 10/min/IP) on both views as part of token-lifecycle work.
   Source: `01-auth-sessions.md` bug 3 (merges `07-api-design.md` #6,
   `08-security-mobile.md` V6).
6. **Roster overlap is check-then-insert, no DB backstop** — surface:
   `POST /api/shift-rosters/`. Repro: two concurrent overlapping POSTs → 201 +
   201 double-booking. Fix: exclusion constraint on
   `(employee, work_date, tstzrange)` or `select_for_update` + re-check in
   `perform_create`. Source: `03-attendance-roster.md` R1.
7. **Leave accepts arbitrary status + inverted dates + negative allocation** —
   surface: `/api/leaves/`, `/api/leave-allocations/`. Repro: PATCH
   `{"status": "Bogus!!!"}` → 200; POST start 05-10/end 05-01 → 201 (inflates
   `remaining`); POST `days_total: "-3.0"` → 201. Fix: `choices=` +
   `validate()` (`start ≤ end`, `MinValueValidator(0)`) on serializers/models.
   Source: `04-leave-ot-swap.md` bugs 1, 2, 8 (merged).
8. **ShiftSwap PUT bypasses the decide guard** — surface:
   `PUT /api/shift-swaps/<id>/`. Repro: reject via PATCH, then PUT
   `{status: Approved}` → 200 Approved with holders NOT swapped, no
   notifications. Fix: route all status writes through guarded `patch()` /
   `perform_update`. Source: `04-leave-ot-swap.md` bug 3.
9. **Correction approve→reject doesn't revert; PUT bypasses application** —
   surface: `/api/attendance-corrections/<id>/`. Repro: approve (row 08:30/
   17:30), PATCH Rejected → 200 but row keeps corrected times; PUT Approved →
   200 but row never updated. Fix: revert-to-prior on reject (+ audit); route
   PUT through the guarded handler. Source: `04-leave-ot-swap.md` bugs 4, 5
   (merged).
10. **Duplicate overtime slips per attendance** — surface: `POST /api/overtime/`.
    Repro: two POSTs same attendance → 201 + 201, each approvable with its own
    payroll notification. Fix: unique constraint on `OvertimeSlip.attendance`
    (one slip per attendance). Source: `04-leave-ot-swap.md` bug 6.
11. **Anonymous signup is an enumeration oracle + role mass-assignment** —
    surface: `POST /api/employees/` (AllowAny). Repro: unknown → 201, known →
    409, no auth; anon can set `role: "Admin"` / `is_active`. Fix: uniform
    `202 Accepted` + CAPTCHA/carve-out + `read_only` on `is_active`/`role`.
    Source: `08-security-mobile.md` V5.

### MED

12. **Unhandled 500s: update-path 409s + bad-param ValidationErrors** —
    surface: `PATCH employees` case-variant dup email → 500; colliding
    allocation PUT/PATCH → 500; `conflicts/?employee=xxx` / bad date → 500;
    `purge-run {"days": -5}` → `CommandError` 500. Fix: map `IntegrityError` →
    409 and catch `ValidationError`/`ValueError`/`CommandError` → 400 in the
    affected views. Source: `02-employees.md` bug 4 + `07-api-design.md` #7 +
    `05-payroll-claims-purge.md` B1, B2 (merged).
13. **Roster/directory truncation: main loader ignores `page_size`, lookup @50,
    dept map page-1-only** — surface: directory + offboard + dept filter.
    Repro: 11 employees → 11th never renders (`GET /api/employees/` bare vs
    default page 10); staff #51+ offboard → "No employee found"; >10 depts →
    `data-dept=''` misses filter. Fix: `?page_size=100` (or follow `?search=`)
    on directory/offboard/dept fetches; refresh directory after offboard.
    Source: `02-employees.md` bugs 1, 2, 7 (merged).
14. **Deleting an Approved leave silently restores balance, no audit** —
    surface: `DELETE /api/leaves/<id>/`. Repro: DELETE approved 2-day leave →
    204, `used` 2 → 0, no audit row. Fix: guard/block delete of Approved or
    write audit + notification. Source: `04-leave-ot-swap.md` bug 7.
15. **`?next=` open redirect after login** — surface: `handleAuthLogin`.
    Repro: `/login/?next=https://evil.example/` + valid login → navigates
    off-site. Fix: accept only same-origin paths (`^/(?!/)`).
    Source: `01-auth-sessions.md` bug 1.
16. **`showToast` drops `type` (errors look like info)** — surface: all ~40
    `showToast(msg, 'error')` calls. Repro: trigger any error toast → styled
    identically to info (fallback dead: hoisted function defeats the
    `typeof` guard). Fix: fold `type` styling into the primary definition,
    delete dead fallback. Source: `02-employees.md` bug 5 (merges
    `06-frontend-ux.md` bug 7).
17. **Attendance update validation gaps** — surface: `PATCH
    /api/attendance/<id>/`, `POST /api/attendance/`. Repro: PATCH
    `{clock_out: T-1h}` → 200 inverted shift; POST without `clock_in` → 201
    null occupying the open slot. Fix: time-order check in serializer
    create+update; require `clock_in` (default now). Source:
    `03-attendance-roster.md` B1, B2 (merged).
18. **Negative `net_pay` accepted; processed runs unlocked** — surface:
    `POST/PATCH /api/payroll-items/`. Repro: base 100 / deductions 200 → 201
    net `-100.00`; lines editable after `is_processed=True`. Fix: non-negative
    guard + lock lines on processed runs (product call). Source:
    `05-payroll-claims-purge.md` B6.
19. **Conversation-key default mismatch hides new messages** — surface:
    `/api/messages/`. Repro: POST without key → lands in `"general"`, bare GET
    reads `"sarah"` → message invisible. Fix: single constant for model + list
    + create defaults. Source: `05-payroll-claims-purge.md` B5 (merges
    `07-api-design.md` #5).
20. **Unrestricted chat upload; DEBUG-only media serving** — surface:
    `Message.attachment` + `/media/`. Repro: POST any file type/size → stored
    at guessable `/media/message-attachments/…` (404 when `DEBUG=off`). Fix:
    MIME/size allowlist + randomized names + real storage/signed URLs.
    Source: `08-security-mobile.md` V7.

## Deliberately-dropped (with reasons)

- **Secrets rotation in git history (`08` V4):** human's job — noted here, not
  tasked. No history rewrite without coordination (shared branch).
- **Mobile blockers (`08` §Mobile 1–6):** out of standing scope (desktop
  ADMIN-ONLY). Inherits V1–V3 fixes when mobile ships.
- **Demo/LIVE badge, activity feed, dead tbody loaders, leave-register loader,
  tour wording, KPI Applicants, `Greetings, gurt!` (`06` bugs 1–6, 9–10,
  honesty §):** accepted posture — disclosed static-vs-live with honest
  fallback toasts; demo-badge/grievance-note posture already agreed. Not
  re-tasked except where a toast falsely claims persistence (those stay:
  roster assign/remove #20-adjacent, promote/transfer, grievance outcomes —
  covered by the `03` B3 wire-or-label rule; individual toast instances not
  listed to hold the cap).
- **Roster Assign/Remove DOM-only demo (`03` B3, `06` honesty):** merged into
  the wire-or-label rule; not a separate ranked item (cap). Fix remains: wire
  Assign to `POST /api/shift-rosters/` (surface 409s) or label "draft preview
  — not saved".
- **Contract nits (`07` #1–4, roster/PATCH-only notes):** `{message}` vs
  `{error}` split, claim-status 200-vs-201, employee DELETE 200-vs-204, flat
  field-errors — documented tradeoffs, no behavior fix; dropped for cap.
- **Missing-surface/test gaps (`07` §Missing, 429 shape, PUT/DELETE coverage,
  anon-denied per-route, pagination clamping):** test-coverage work, no
  user-facing bug; dropped for cap.
- **LOW UI polish below cap (`01` bug 4 dead routes, `02` bugs 6 onboarding
  residuals / 8 profile-button-profile nits, `03` B4 no punch buttons,
  `05` unwired-frontend notes, `06` bug 8 `escapeHtml(undefined)`):**
  harmless/dead-code/polish or API-only paths with no user impact today.
- **Anon dashboard aggregates (`08` V8), session-hardening defaults (`01`
  security notes), CSRF test gap (`01`):** accepted pilot posture behind
  localhost; must be set before internet exposure, not ranked in the 20.
