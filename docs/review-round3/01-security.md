# 01 — Security & Auth Regression (round 3, @ cf89b71)

Scope: session/token routes, messages/claim-statuses, AllowAny spots, service-role, CORS, keys status. Round-2 settled items verified, not repeated.

## Findings

1. [CRITICAL] Live secrets still in git history — `597d245` (`.env`,
   11 insertions per `--stat`; SECRET_KEY+SERVICE_ROLE+DB_PASSWORD per
   round-2 S1, content not re-opened). Rotation + purge still PENDING.
2. [HIGH] DRF tokens never expire, no rotation — `api/urls.py:102`
   (`obtain_auth_token`). `SessionLogoutView` deletes the token only as a
   side effect (`core/views.py:382-383`). A leaked token is valid forever.
   (Round-2 S2 partly fixed: throttle + session logout now exist; expiry
   is the remainder.) Recommend expiring tokens or rotation on logout/login.
3. [MEDIUM] Onboarding provisions no Django login — `core/views.py:127-143`
   creates a Supabase Auth user + `Employee` row, but `SessionLoginView`
   (`core/views.py:362-377`) authenticates the Django `User` table. An
   onboarded employee has no password login; only `createsuperuser` accounts
   can sign in. Provision a Django user at onboarding or document operator-only auth.
4. [MEDIUM] Message sender is client-supplied — `core/views.py:395-399`
   (`sender_name`, `conversation_key` from `request.data`, defaults
   `"Marcus Williams"`/`"sarah"`); `Message.sender_name` is a free CharField
   (`core/models.py:138`). Any authed user can post as anyone into any
   conversation. Bind sender to `request.user`, make `sender_name` read-only.
5. [MEDIUM] Claim status overwritable by any authed user —
   `core/views.py:406-412` (`update_or_create` on client `claim_id`/`status`);
   serializer strips `claim_id` validators (`core/serializers.py:178`) and no
   status-choice validation is visible. Needs status choices + role check.
6. [MEDIUM] No brute-force protection on credential endpoints beyond the
   global `anon 100/day` throttle — `api/urls.py:102-104`,
   `kumon_ems/settings.py:187-191`. No lockout or scoped rate. Fine for
   pilot; tighten before internet exposure.
7. [LOW] `SessionLogoutView` mixes schemes — `core/views.py:380-385` deletes
   the DRF token AND the session; a token-script caller hitting it silently
   kills its token. Documented in README auth contract; keep.
8. [LOW] `DashboardSummaryView` still `AllowAny` — `core/views.py:59-63`
   (intentional, `:62` B10; settled S8, no regression; counts oracle accepted).
9. [LOW] CORS unchanged localhost-only + credentials —
   `kumon_ems/settings.py:167-174` (settled S7, no regression). Safe for dev;
   prod needs env-driven allowlist (currently hardcoded, no override).
10. [LOW] Service-role still 3 call sites, all server-side —
    `core/views.py:131,154`, `purge_resigned.py:35`; key loaded only in
    `core/supabase_client.py:11`, zero secret/`Authorization` hits in
    `static/`. Settled S4, no regression, no client leak.

## Fixed since round 2 (not findings)

- Purge fail-CLOSED (`:33-43`, skip in `atomic()`), `--days` rejects
  negatives (`:25-26`), audit row written (`:36-39`). Left: manual-only,
  `--days 0` allowed, no confirm. (`purge_resigned.py`)
- Soft-delete: honest 200+`purge_on` + resigned audit log; re-DELETE no
  longer resets `resigned_at` (`core/views.py:175-199`).
- Throttle `anon 100/day, user 1000/day`, `PAGE_SIZE 10`, `EXCEPTION_HANDLER`
  now set (`kumon_ems/settings.py:185-193`).

## Verdict

No new Critical beyond pending history rotation (#1). Prod blockers: token
expiry (#2), login gap (#3), message/claim write-auth (#4, #5).
