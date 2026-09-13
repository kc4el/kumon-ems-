# 05 — Auth & Sessions edge cases (round 4 @ 4c6864c)

Scope: onboarding→login→session/token→offboard/purge chain, `?next=`, per-user scoping.
Round-3 carried items re-checked: token-no-expiry, onboarding-no-login, anon-throttle-only
still open; message-sender binding (`core/views.py:719-723` + `serializers.py:285-291`
read-only) and claim-status atomic upsert (`core/views.py:736-746`) are FIXED, not repeated.

## Findings

1. [HIGH] Purge/offboard orphan the Django credential — `purge_resigned.py:33-45`
   deletes Supabase user + `Employee` row but never the Django `User`
   (`core/views.py:175-181`) or its DRF token; `EmployeeDetailView.destroy`
   (`core/views.py:213-237`) likewise leaves both. A resigned+purged employee's
   token stays valid forever (compounds never-expiring tokens). Delete
   `User`+token in the same atomic block.
2. [MED] Browser logout never revokes the DRF token — `core/views.py:704-709`
   deletes `request.auth` only when set; under `SessionAuthentication`
   `request.auth` is `None`, so session-logout leaves the user's token alive.
   Also delete `Token.objects.filter(user=request.user)`.
3. [MED] `?next=` open redirect after login — `dashboard.js:1256-1257`
   `window.location.href = next` with raw query value; crafted
   `/login/?next=https://evil…` navigates off-site post-auth. Accept only
   same-origin paths (`^/(?!/)`).
4. [MED] Notifications unscoped cross-user — `core/views.py:759-761` lists ALL
   rows; `NotificationMarkReadView` (`:764-769`) `get_object_or_404` with no
   ownership check. Any authed user reads/marks anyone's notifications.
   Filter by `request.user`→employee + check owner on PATCH.
5. [MED] `is_staff` never set in prod — onboarding `create_user`
   (`core/views.py:175-181`) passes no `is_staff`; only `createsuperuser`
   (CLI) or tests (`api/tests.py:804`) grant it. `PurgeRunView`
   (`core/views.py:772-773`, `IsAdminUser`) is unreachable from the app, so
   SOP S5 purge depends on undocumented CLI bootstrap. Seed or gate
   first-admin explicitly.
6. [MED, carried] Passwordless onboarded users can never log in —
   `core/views.py:134,172`: no `password` ⇒ no `User`; `SessionLoginView`
   (`:686-701`) authenticates the `User` table only. Browser signup always
   sends one (`dashboard.js:1276`), so only direct-API onboard hits it.
7. [LOW] Re-onboard after purge permanently bricked — `Employee` row gone so
   the `email__iexact` guard (`core/views.py:150`) passes, Supabase create
   succeeds, then duplicate `User.username` raises `IntegrityError` inside
   the atomic block → misleading 409 "already exists" (`:183-188`) + Supabase
   rollback every retry. Follows from #1; clear orphan `User` on purge.
8. [LOW] Email enumeration via onboarding oracle — AllowAny POST returns 409
   "already exists" vs 201 (`core/views.py:150-154`). Login itself is generic
   ("Invalid credentials.", `:696-699` — good); throttle (`100/day`, only
   mitigation) bounds but doesn't close it.
9. [LOW] Audit log readable by any authed user — `EmployeeAuditLogListView`
   (`core/views.py:681-683`) unscoped; resign/purge records visible to all
   employees. Restrict to staff or self-rows.
10. [LOW] Sessions: fixation OK (Django `login()` cycles the key,
    `core/views.py:700`), but no hardening — zero `SESSION_*` in
    `kumon_ems/settings.py`: default 2-week persistent cookie, no idle
    timeout, `Secure` off. Set `SESSION_COOKIE_AGE` + idle expiry before
    internet exposure.
