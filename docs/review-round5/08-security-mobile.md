# Security & mobile-readiness — review round 5

Scope: owner-scoping/IDOR per endpoint, role gates, stored-XSS vectors, secrets
(history vs working tree), Supabase service-role confinement, resigned-auth
window post-T6, anon POST enumeration, mobile blockers.
Branch: `chore/standard-format`. Method: read-only static review, no dev server,
no key rotation, `.env` untouched (values never printed; key names only).

## Verified safe (evidence)

### 1. Supabase service-role key is server-only — zero browser usage
- `core/supabase_client.py:10-16` builds the client from `SUPABASE_URL` +
  `SUPABASE_SERVICE_ROLE_KEY` at import time; the only importers are
  `core/views.py:56` (employee create `176-186`, rollback `209`, resign deauth
  `242`) and `core/management/commands/purge_resigned.py:9,36` (purge retry).
- Grep over `static/`, `pages/`, `index.html`, `templates/` for
  `supabase|createClient|SERVICE_ROLE|apikey` returns **zero hits** — no anon
  key, no service-role key, no Supabase client in any shipped JS/HTML.
- `static/js/dashboard.js:23-46` (`apiFetch`) talks only to same-origin
  `/api/*` with session cookies + CSRF; no `Authorization` header, no token in
  `localStorage`/`sessionStorage` (only widget/tour prefs at `dashboard.js:249,
  260,358,372,443`).

### 2. Stored-XSS sinks are escaped on every live render path
- Single escaper `escapeHtml` at `static/js/dashboard.js:1218-1220`
  (`&<>"'` → entities). Every `innerHTML` interpolation of API/user data wraps
  it: directory cards (`1519-1531`), attendance (`1589-1591`), roster
  (`1621-1625`), payroll (`1679-1682`), audit log (`1720-1724`), activity feed
  (`333`), shift-slot rows (`759-762`). Non-interpolated `innerHTML` targets
  are static strings (`No records yet`, `Loading…`, inline SVG chevrons at
  `456,462`) or internal nav constants (breadcrumb `184-186`).
- Chat (highest-risk surface: free-text `Message.text` + `sender_name`) never
  touches `innerHTML`: `appendPersistedMessage` (`dashboard.js:1158-1182`)
  builds DOM nodes and assigns `textContent`; attachment links set
  `link.textContent` with `rel="noopener"` + `target="_blank"`.
- No `|safe` / `autoescape off` in any Django template (`pages/`, `index.html`,
  `core/` grep clean); toast (`841-847`) and tour text (`387-421`) use
  `textContent`.
- Residual nit (not a vuln): `escapeHtml` assumes a string (`.replace` on the
  receiver). All current call sites pass strings or `String(...)` except
  `emp.role || ''` (`1520`) — safe today because `role` is a CharField/null,
  but a future non-string field passed raw would throw, not execute.

### 3. `purge-run` is the only role-gated endpoint, and it holds
- `core/views.py:801-802` `PurgeRunView.permission_classes = [IsAdminUser]`;
  default for everything else is `IsAuthenticated`
  (`kumon_ems/settings.py:182-184`). No bypass path: the view calls
  `purge_resigned` with the caller's `days`/`dry_run` only, no raw command
  passthrough (`core/views.py:804-830`).
- Resign path (post-T6, commit `26a4e44`) does revoke Supabase Auth at resign
  time: `EmployeeDetailView.destroy` → `supabase.auth.admin.delete_user`
  (`core/views.py:240-245`), fail-open with `deauthed=` flag in the response
  (`253-262`) and a distinct audit row (`246-252`); `purge_resigned.py:28-48`
  retries the Supabase delete before hard-deleting the row. Fail-open is the
  documented choice so a Supabase outage can't block the HR action.

### 4. Secrets in the working tree are correctly scoped
- `.env` is gitignored (`.gitignore`: `.env`, `db.sqlite3`, `__pycache__`) and
  **untracked** (`git ls-files | grep env` empty); working-tree `.env` holds
  `DEBUG, SECRET_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DB_*` (key names
  only — values never read), which is the expected local-dev posture.
- `kumon_ems/settings.py:29-34` refuses to boot without `SECRET_KEY` when
  `DEBUG` is off; `core/supabase_client.py:13-14` raises on missing Supabase
  credentials instead of falling back to an anon key.

## Vulnerabilities (severity + repro)

### V1 — HIGH — No owner scoping: any authenticated employee can PATCH/DELETE anyone's records (IDOR, all detail endpoints)
Every `RetrieveUpdateDestroyAPIView` uses an unscoped `queryset = <Model>.objects.all()`
with no `get_queryset` filter on `request.user` and no object permission:
`DepartmentDetailView` (`core/views.py:110-112`), `EmployeeDetailView`
(`221-223`), `AttendanceDetailView` (`277-279`), `AttendanceCorrectionDetailView`
(`294-296`), `LeaveRequestDetailView` (`411-413`), `LeaveAllocationDetailView`
(`430-432`), `OvertimeSlipDetailView` (`510-512`), `ShiftRosterDetailView`
(`553-555`), `ShiftSwapDetailView` (`563-565`), `PayrollRunDetailView`
(`657-659`), `PayrollItemDetailView` (`688-693`), `PerformanceReviewDetailView`
(`701-703`), `ExpenseClaimDetailView` (`783-785`), `NotificationMarkReadView`
(`793-798`, `get_object_or_404(Notification, pk=pk)` — any user's notification).
There is no `User ↔ Employee` link anywhere (grep `request.user` in
`core/,api/` hits only `core/views.py:749` for chat display names), so scoping
cannot even be expressed today.
Repro (authenticated as any non-admin employee): `PATCH /api/employees/<other-uuid>/`
`{"last_name":"X"}` → `200`; `DELETE /api/leaves/<other-uuid>/` → `204`;
`PATCH /api/notifications/<other-uuid>/read/` → `200` marks someone else's
notification read. Same pattern reaches payroll and performance reviews.

### V2 — HIGH — No role gates: any authenticated user can approve/reject, edit payroll, resign anyone
Only `PurgeRunView` sets `IsAdminUser` (`core/views.py:802`). All approval
mutations are open to any login: attendance-correction approve/reject
(`298-346`), shift-swap approve/reject incl. roster reassignment (`577-608`,
`_approve_swap` `611-649`), overtime status (`514-517`), leave/OT/claim status,
payroll-run/item create/update/delete (`652-693`), and `DELETE
/api/employees/<uuid>/` which **resigns anyone** (`230-262`) — there is no
"self or HR" check. `Employee.role` (`core/models.py:33`) is a free-text label,
not an auth role, so it gates nothing.

### V3 — HIGH — Resigned staff keep Django/DRF access: resign revokes Supabase only, never the local User, token, or session
Signup creates a persistent `django.contrib.auth.models.User`
(`core/views.py:190-198`), and auth is `SessionAuthentication` +
`TokenAuthentication` (`kumon_ems/settings.py:178-181`). The resign path
(`core/views.py:230-262`) deletes only the Supabase user (`242`); grep for
`Token.objects|Session.objects|flush|delete.*token` in `core/,api/,kumon_ems/`
(excl. tests) finds **nothing** — the local `User` row, its DRF token
(`api/urls.py:161` `auth-token/`), and any live sessions survive resign
indefinitely. Combined with the fail-open Supabase branch (`240-245`,
`deauthed=false` + retry only at 30-day purge), a resigned employee whose
Supabase delete fails keeps **both** auth planes until `purge_resigned` runs —
and even on success keeps the Django/token plane forever. Repro: create user →
`POST /api/auth-token/` (token A) → `DELETE /api/employees/<self>/` as another
user → `GET /api/employees/` with `Authorization: Token A` still → `200`.
Fix (human-approved): on resign, delete the `User` row(s) for that email,
`Token.objects.filter(user=...).delete()`, and flush that user's sessions;
treat Supabase failure as today but also suspend locally first.

### V4 — HIGH (human job, still open) — Live secrets remain in git history; rotation not done
`.env` was committed in `597d245` and only untracked in `c5bd55f`
(`git log --all -- .env` shows both); the history diff still contains
`SUPABASE_SERVICE_ROLE_KEY=eyJhbG…`, `SECRET_KEY`, `DB_PASSWORD`. Working-tree
`.env` still carries live values (expected for local dev). Prior rounds already
flagged this (`docs/review-round3/01-security.md:8`,
`docs/iso25010/JUSTIFICATION-AND-IMPROVEMENTS.md:13`); rotation (Supabase key +
`SECRET_KEY` + DB password) is still the outstanding human action. Do not
rewrite history without coordinating — the branch is shared.

### V5 — MEDIUM — Anonymous signup is an email-enumeration oracle + mass-assignment
`EmployeeListCreateView.get_permissions` returns `AllowAny` for POST
(`core/views.py:136-141`), by design for self-service signup. But the status
codes distinguish states without auth: unknown email → `201` (`199`), known
email → `409` (`167-171`), missing email → `400` (`147-150`), weak password →
`400` (`158-161`), Supabase down → `502` (`215-218`). An attacker can probe the
employee directory one email at a time, throttled only by `anon 100/day`
(`kumon_ems/settings.py:191`) — slow but reliable, and each probe also learns
password-policy rejections for free. Additionally `EmployeeSerializer:32-45`
leaves `is_active`, `role`, `department` writable, so an anonymous caller can
self-create with `role:"Admin"` or `is_active:false` (no privilege attached
today per V2, but it poisons HR data and pre-empts the role model). Consider:
uniform `202 Accepted` response (async provision), CAPTCHA/rate-limit carve-out
for this route, and an explicit `read_only`/`extra_kwargs` allowlist
(`is_active`, `role` server-set).

### V6 — MEDIUM — `session-login` deliberately exempt from throttling (brute-force surface)
`SessionLoginView.throttle_classes = []` (`core/views.py:711-716`, comment cites
shared-office-IP lockout as the reason; hardening "deferred to token-lifecycle
work"). `auth-token/` (`api/urls.py:161`) keeps the default `anon 100/day`, so
password guessing simply moves to the unthrottled session endpoint, which
returns a session cookie on success (`718-730`) with distinct `401` on failure
— a clean oracle. No lockout, no CAPTCHA, no `AXES`-style counting. Acceptable
only behind the planned lifecycle work; until then, at minimum add a
route-specific throttle less aggressive than the global anon bucket.

### V7 — MEDIUM — Unrestricted chat file upload, predictable media URLs, DEBUG-only serving
`Message.attachment` is a bare `FileField` (`core/models.py:227-229`) with no
content-type/size/extension validation anywhere (grep `content_type|file_size|
FILE_UPLOAD` in `core/` empty); `MessageSerializer:270-305` requires only
text-or-file. `MessageListCreateView.perform_create` (`748-752`) stamps
`sender_name` from the session but ignores the client-sent `sender_name` only
because the serializer marks it read-only (`285-291`) — correct, but the stored
file itself is unvalidated. `MEDIA_URL` is served via
`kumon_ems/urls.py:28` **only when `DEBUG` is on** (plus an `insecure` static
serve at `30-32`), so attachments 404 in any `DEBUG=off` deploy, while in dev
they sit at guessable `/media/message-attachments/YYYY/MM/DD/<filename>`.
Add server-side MIME/size allowlist, randomize storage names, and serve media
from real storage in production.

### V8 — LOW (accepted risk, note for mobile) — Anonymous dashboard aggregates leak headcounts
`DashboardSummaryView.permission_classes = [AllowAny]` (`core/views.py:69-73`,
comment "intentional; see B10") exposes `total_employees`, `active_employees`,
approved/pending leave counts, open attendance rows to anyone. Fine for the
desktop landing page; a future mobile client must not treat these as public —
scope or re-gate them when the app ships.

## Mobile blockers

Standing architecture is desktop ADMIN-ONLY with employees reaching the system
only via a future mobile app. Nothing mobile exists yet; the items below are
what blocks it, ordered by dependency.

1. **No self-service API surface (blocked by V1/V2).** Every endpoint returns
   the full tenant queryset; there is no `GET /api/me/*`, no `?mine` scoping,
   no owner filter. A mobile app cannot offer "my leaves / my roster / my pay"
   without either over-fetching everyone's data (privacy breach at scale) or a
   new scoped endpoint family. Fix V1/V2 first; mobile inherits the design.
2. **Auth is browser-session-only.** The web client uses session cookies + CSRF
   (`dashboard.js:23-46`); DRF tokens exist (`auth-token/`, `settings.py:180`)
   but never expire, are never rotated, and survive resignation (V3). A mobile
   app needs token lifecycle (expiry/refresh/revoke-on-resign, per-device
   tokens) — the "deferred token-lifecycle work" cited at `core/views.py:715`
   is a mobile prerequisite, not a nice-to-have.
3. **Resigned-device window (V3 amplified).** Long-lived mobile tokens + no
   server-side revocation means a resigned employee's phone keeps API access
   until someone manually deletes the token. Device/employee offboarding must
   kill tokens and sessions (see V3 fix).
4. **Push does not exist.** `Notification` rows (`core/models.py:242-251`) are
   in-app only, pulled on page load (`dashboard.js` audit/log loaders); no FCM/
   APNs wiring, no badge counts, no background delivery. Leave decisions,
   shift assignments, overtime approvals (signals in `core/signals.py:
   notify_leave_decision`, `notify_shift_assignment`, `notify_overtime_approval`)
   create DB rows only.
5. **Attachments won't survive staging (V7).** Media serving is DEBUG-gated
   (`kumon_ems/urls.py:28`); a mobile client uploading expense/chat attachments
   against a `DEBUG=off` backend gets 404s on read-back. Needs real object
   storage + signed URLs before any mobile upload feature.
6. **Layout is desktop-first; mobile UX unverified.** `viewport` meta is present
   (`pages/dashboard.html:6`) and `@media (max-width:1200px/768px)` rules exist
   (`static/css/main.css:3823-3890`), but the messages view is a fixed
   full-viewport app layout (`main.css:2827`), roster/attendance/payroll are
   wide tables re-rendered via `innerHTML`, and auth pages key off `file:`
   vs `/login/` paths (`dashboard.js:1325-1345`). No device testing has been
   done; budget a mobile pass (touch targets, table→card collapse, offline/
   retry, `apiFetch` 401→login redirect is web-only behavior at
   `dashboard.js:39-43`).
