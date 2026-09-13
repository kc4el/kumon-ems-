# 04 — Frontend Wiring & UX (round 3 @ cf89b71)

`node --check static/js/dashboard.js` → exit 0. Note: live calls now split between
`apiFetch` wrapper and raw `fetch`, so `grep -n 'fetch('` undercounts live wiring.

## Live vs static inventory (`static/js/dashboard.js` unless noted)
- LIVE via `apiFetch` (CSRF + 403→login + badge): summary `:1122-1147`,
  directory `:1154-1197`, onboarding POST `:292`, leave POST `:676-704`,
  logout `:1005`. Auth fix since R2 is real for these paths.
- LIVE via raw `fetch` (NO CSRF/credentials/403→login/badge — [HIGH]):
  claims load/save `:581`,`:592-596`; messages load/send `:806-808`,`:871`.
- Login WIRED `:933-961` — real POST `/api/session-login/`, honors `?next=`
  `:957`, inline error, deliberately bypasses `apiFetch` `:937-938`. (R2-F3 fixed.)
- Signup MOCK (persists, [MED]): `handleAuthSignup` `:963-990` toast-only, no POST.
- STATIC toast-only (no POST, [LOW] unless labeled): grievance `:321`,
  advance `:646`, offboarding `:253`, roster update `:369`, shift remove `:491`,
  audit CSV export `:1067`, pagination toasts (`index.html:3671-3673`).

## Findings
1. [HIGH] Claims/messages bypass `apiFetch` — no CSRF, no credentials, no
   `403→/login/?next=`, never touch `#apiModeBadge`. `dashboard.js:581,592,806,871`.
2. [MED] Signup still mock `:963-990` (no endpoint call); adjacent to real login —
   users can't distinguish. Wire or remove.
3. [MED] `apiFetch` handles only 403 `:29`; 401/419 pass through silently.
4. [LOW] `confirmAddStaff` purely local (no POST) but sets badge `Draft` `:457` —
   honest label, keep. `Allocation (demo)` label `:367` good (R2-F1/F2 improved).
5. [LOW] No loading states anywhere — no spinner/skeleton; no double-submit guard
   on onboarding/leave/claims/messages POSTs.
6. [LOW] Empty states thin: shift placeholder `:482` only; directory wipe `:1165`
   has no "no employees" message; claims/messages failures toast-only, badge stale.
7. [INFO/FIXED vs R2-F10] `confirmAddStaff` now escapes all interpolations
   `:442,444-445`; directory render escaped `:1181-1182`. `escapeHtml` `:891-893`.
8. [INFO] `#apiModeBadge` wired only by summary/directory paths
   (`setApiMode` `:34-42`, element `core/templates/core/index.html:103`,
   default `DEMO DATA`); claims/messages outcomes never reflected.
9. [LOW] Onboarding validation still naive: first/rest name split `:286-290`, no
   email/role/department fields sent; login page ships prefilled demo creds
   (`login.html:44,51` + "demo credentials" note) — fine for dev, strip before pilot.
