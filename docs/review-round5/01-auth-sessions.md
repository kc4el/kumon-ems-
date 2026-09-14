# 01 — Auth & Sessions (round 5 @ chore/standard-format)

Scope: `SessionLogin`/`SessionLogout`, `auth-token` endpoint, signup flow,
session-vs-token split, anon/user throttle (100/day anon), CSRF on session calls.
Edge cases attempted: bad creds, expired token, throttled login (exempt per `fb68b57`).

## Verified working (with test evidence)

All runs: `DB_HOST= TZ=UTC ./.venv/Scripts/python manage.py test <labels>`
(11 tests, all OK).

1. **Session login/logout round trip** — `POST /api/session-login/`
   (`api/urls.py:162`, `core/views.py:711-730`) sets a `sessionid` cookie on
   good creds; authed `GET /api/employees/` → 200; `POST /api/session-logout/`
   (`api/urls.py:163`, `core/views.py:733-738`) → 200 and subsequent GET → 403.
   Evidence: `api/tests.py:1113-1127` (`SessionAuthTests.\
   test_session_login_logout_round_trip`) — PASS.
2. **Bad creds → generic 401** — wrong password returns 401
   `{"error": "Invalid credentials."}` (`core/views.py:724-728`), no
   user-enumeration delta. Evidence: `api/tests.py:1103-1111` — PASS.
3. **Token endpoint issues tokens; anon otherwise 403** — anon
   `GET /api/employees/` → 403, public `GET /api/dashboard-summary/` → 200,
   `POST /api/auth-token/` → 200 `{"token"}` (`api/urls.py:161`).
   Evidence: `api/tests.py:30-38` — PASS.
4. **Signup provisions login iff password given** — AllowAny
   `POST /api/employees/` (`core/views.py:136-141`) with `password` validates
   via `validate_password` (weak → 400, `core/views.py:151-161`), creates
   Supabase user + `Employee` + Django `User(username=email)` atomically
   (`core/views.py:172-199`); the new user can `session-login`
   (`api/tests.py:795-800`). No password → no `User` row. Duplicate email →
   409 (`core/views.py:167-171`). Evidence: `api/tests.py:778-834` (3 tests) —
   PASS.
5. **Throttle exemption for session login (fb68b57)** — `SessionLoginView.\
   throttle_classes = []` (`core/views.py:716`) with rationale comment
   (`:713-715`); one office IP sharing the anon 100/day quota can no longer
   lock everyone out of login. Verified by introspection
   (`SessionLoginView.throttle_classes == []`) and commit diff `fb68b57`.
   Rates still configured: `anon 100/day`, `user 1000/day`
   (`kumon_ems/settings.py:187-191`, `api/tests.py:689-693` — PASS).
6. **Session/token split is real and documented** — browser JS sends no
   `Authorization` header anywhere (`static/js/dashboard.js`: zero matches);
   all API calls go through `apiFetch` with `credentials: same-origin` + CSRF
   (`dashboard.js:28-46`); tokens are operator/script-only per
   `README.md:18-19`. Auth backends order session-first
   (`kumon_ems/settings.py:178-181`), default permission `IsAuthenticated`
   (`:182-184`).
7. **CSRF wired on session calls** — `CsrfViewMiddleware` active
   (`kumon_ems/settings.py:66`); `apiFetch` attaches `X-CSRFToken` for JSON
   and FormData (`dashboard.js:29-36`); login/signup use raw `fetch` but still
   send the header + `same-origin` (`dashboard.js:1266-1271`, `:1298-1304`).
8. **Canonical auth routes** — `/signup/` and `/auth/` 302 → `/login/`
   (`kumon_ems/urls.py:14-15`); the JS signup card posts a real
   `POST /api/employees/` then redirects to `/login/?next=/`
   (`dashboard.js:1300-1317`). Evidence: `core/tests.py:263-267` — PASS.

## Bugs found (repro steps)

1. **[MED] `?next=` open redirect after login still open** (round-4 carryover).
   `handleAuthLogin` trusts the raw query value:
   `static/js/dashboard.js:1284-1285`
   (`const next = new URLSearchParams(...).get('next') || '/';
   window.location.href = next;`).
   Repro: visit `/login/?next=https://evil.example/`, sign in with valid
   creds → browser navigates off-site. (`apiFetch`'s own bounce is safe —
   it uses `pathname` only, `:42-43`.) Fix: accept only same-origin paths
   (`^/(?!/)`).
2. **[MED] Session logout never revokes the DRF token** (round-4 carryover).
   `SessionLogoutView.post` (`core/views.py:733-738`) deletes `request.auth`
   only when set; under `SessionAuthentication` `request.auth` is `None`, so
   the token survives. Repro: `POST /api/auth-token/` → save token;
   session-login in browser → `POST /api/session-logout/` → reuse saved
   token with `Authorization: Token …` → still 200. Fix: also delete
   `Token.objects.filter(user=request.user)`.
3. **[MED] `auth-token/` is unthrottled — `fb68b57` exempted only half the
   credential surface.** DRF 3.18 hardcodes `throttle_classes = ()` in
   `ObtainAuthToken` (`.venv/.../rest_framework/authtoken/views.py:9`;
   introspected `ObtainAuthToken.throttle_classes == ()`), so the exemption
   rationale was never the only hole: unlimited password-guessing against
   `/api/auth-token/` never 429s. Repro: loop `POST /api/auth-token/` with
   bad passwords → always 400, never 429. Fix: scoped throttle on the token
   view (e.g. burst 10/min) as part of the deferred token-lifecycle work.
4. **[LOW] Dead duplicate auth routes in `core/urls.py`.**
   `core/urls.py:8-9` maps `signup/` and `auth/` to `login_view`, but
   `kumon_ems/urls.py:14-15` redirects those paths before `core/` is reached
   (and `core/` is mounted at `core/`, so these serve `/core/signup/`,
   `/core/auth/` rendering the login page at odd URLs). Harmless but
   confusing; delete or redirect like the canonical ones.
5. **[LOW, carried] Resign/purge still orphan the Django credential.**
   `EmployeeDetailView.destroy` (`core/views.py:230-260`) and
   `purge_resigned.py:33-49` delete the Supabase user + `Employee` row but
   never the Django `User` (`core/views.py:192-198`) or its token — so a
   resigned/purged employee's token stays valid (compounds #2/#3 and the
   never-expiring token), and re-onboarding the same email hits a duplicate
   `username` `IntegrityError` → misleading 409. Fix: delete `User`+token in
   the same block.

## Security notes

- **Tokens never expire** (round-2/3/4 carryover, still true): `Token` fields
  are only `key/user/created` (introspected); no Knox/JWT/rotation; no
  `expir|refresh` logic in `core/views.py`, `api/urls.py`,
  `kumon_ems/settings.py` (grep: no matches). A leaked token is valid until
  manual deletion. "Expired token" edge case is therefore N/A — worth stating
  explicitly since the brief asked for it.
- **No session hardening**: zero `SESSION_*`/`CSRF_*`/`SECURE_*` in
  `kumon_ems/settings.py` (grep: only hit is `XFrameOptionsMiddleware`,
  `:69`) — default 2-week persistent cookie, no idle timeout, `Secure` off.
  Fine for pilot behind localhost, must be set before internet exposure.
- **Anon signup spam surface unchanged**: AllowAny `POST /api/employees/`
  creates Supabase user + usable Django login; only mitigations are global
  anon 100/day (shared-IP caveat per `fb68b57`) and the 409-vs-201 email
  oracle (`core/views.py:167-171`). No captcha/rate carve-out — accepted risk
  for self-service signup, but don't expose wider than needed.
- **Test gap (CSRF)**: DRF's test client does not enforce CSRF, so
  `SessionAuthTests` proves the view logic but not that a real browser
  without `X-CSRFToken` gets 403 on session POSTs. CSRF enforcement rests on
  `SessionAuthentication` defaults + `CsrfViewMiddleware`, covered only by
  code inspection (`dashboard.js` headers + `settings.py:66`), not by a test.
- **Logout throttle is fine**: `SessionLogoutView` keeps default throttles
  (introspected: Anon+User); authed users get the 1000/day user bucket —
  no lockout concern.
