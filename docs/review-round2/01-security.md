# Round-2 Review 01 — Security & Auth (delta since round 1)

Scope: authN/Z, tokens, service-role key, secrets history, CORS, audit of new destructive paths. B1–B10 settled findings are not repeated except for status.

## Findings

| # | Sev | Finding (file:line) |
|---|-----|---------------------|
| S1 | Critical | **Live secrets still in git history — rotation pending (HUMAN JOB).** `.env` committed in `597d245` (SECRET_KEY + `SUPABASE_SERVICE_ROLE_KEY` + `DB_PASSWORD`), only untracked at `c5bd55f`. Fail-fast added (`kumon_ems/settings.py:29-34`) kills the hardcoded fallback (B3 partial), but history still exposes all three. Rotate service-role key, SECRET_KEY, DB password; purge/squash history. |
| S2 | High | **Token auth has no lifecycle.** `api/urls.py:98` issues DRF authtokens (never expire, one per user); no refresh/rotation/revocation/logout endpoint, no `DEFAULT_THROTTLE` in `kumon_ems/settings.py:161-171`. A leaked token is valid forever. Add expiry (e.g. Knox/JWT) + throttle on `auth-token/`. |
| S3 | High | **dashboard.js sends no credential, so all writes fail auth.** Fetches (`static/js/dashboard.js:258,601,952,983`) set neither `Authorization: Token` nor CSRF header. Same-origin GETs ride the session cookie, but POSTs under `SessionAuthentication` without `X-CSRFToken` get 403, which JS misreads as "logged out" (`dashboard.js:264,613,985` → `/login/`). Token from `auth-token/` is never consumed by JS. Decide session+CSRF *or* token header and wire it. |
| S4 | Medium | **Service-role blast radius grew.** Still server-side only (`core/supabase_client.py:11`, no frontend leak — good) and validate-before-create (`core/views.py:109-118`) cut spurious admin calls (B4 fixed). But admin-key call sites went 1→3: create (`views.py:122`), rollback delete (`views.py:139`), purge delete (`core/management/commands/purge_resigned.py:30`). Any view/SSRF bug inherits auth-admin god-mode. Scope admin ops (restricted key/edge function). |
| S5 | Medium | **Purge path is unaudited and unguarded.** `purge_resigned.py:29-33` hard-deletes with no audit row, no `--days` floor, no confirmation, and swallows Supabase errors (`except Exception` → still `emp.delete()`), orphaning the auth user. Log each purge (stdout + `EmployeeAuditLog`/server log) and fail-closed on auth-delete error. |
| S6 | Medium | **Soft-delete audit is ambiguous.** `EmployeeDetailView.perform_destroy` (`core/views.py:155-158`) only fires the generic post_save "updated" signal (`core/signals.py:47-57`) — no resigned/deactivated marker, no actor. Use a distinct action string (e.g. `deactivated/resigned_at=...`). |
| S7 | Medium | **`CORS_ALLOW_CREDENTIALS=True` (`settings.py:158`) + static localhost origins (`settings.py:151-156`).** Fine for dev, but credentialed CORS with `SessionAuthentication` lets any allowed origin make authed calls. Parameterize origins per env before deploy (B10 still open). |
| S8 | Low | **Only anonymous routes: `dashboard-summary/` + `auth-token/` + admin login.** `IsAuthenticated` default (`settings.py:166-168`) now covers everything else (B1 fixed). `AllowAny` on `DashboardSummaryView` (`core/views.py:55`, justified `views.py:54`) exposes counts-only aggregates — acceptable, minor enumeration oracle. `obtain_auth_token` anonymity is by design. |

## Status of round-1 security items
Fixed: B1 (IsAuthenticated default), B4 (validate-first), B6/B7 (409 + locked clock-out), B8 (400/409/502 mapping). Partial: B2 (key still god-mode, more call sites), B3 (fail-fast yes, rotation no), B10 (AllowAny documented, CORS still dev-wide). Open human job: S1 rotation.
