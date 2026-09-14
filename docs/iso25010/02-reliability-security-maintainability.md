# 02 — Reliability, Security, Maintainability (ISO/IEC 25010)

Scope: HEAD `cf89b71` on `chore/standard-format` (read-only; no code changes).
Note: many `docs/review-round2/COMPILED.md` (@`c8690ed`) findings are already fixed here — verdicts below assess current files, not the old snapshot.

## 1 Reliability
- Maturity — PARTIAL: 409 fast-paths fixed (`core/views.py:145-150,211,223,336`, `core/serializers.py:56,103`) + unified envelope (`core/exception_handler.py:4-26`) + throttles (`kumon_ems/settings.py:187-191`); races still validate-only, no DB overlap constraint.
- Availability — PARTIAL: SQLite default / Postgres when `DB_HOST` set (`kumon_ems/settings.py:95-114`); dev `runserver` only (`README.md:75`); no backup/restore, no scheduler/cron for purge, no healthcheck.
- Fault tolerance — PARTIAL: dup→409 / upstream→502 mapping (`core/views.py:151-163`) + atomic employee create; clock-out `select_for_update` no-op on SQLite; no retry/circuit-breaker on Supabase calls.
- Recoverability — PARTIAL: purge now fail-closed + audited in-txn (`core/management/commands/purge_resigned.py:33-45`, `--days>=0` at `:25-26`) + Supabase rollback on DB fail (`core/views.py:152-158`); no backups, purge manual-only, CASCADE still wipes payroll/attendance.

## 2 Security
- Confidentiality — FAIL: live SECRET_KEY + SERVICE_ROLE + DB_PASSWORD committed in `597d245` `.env` (untracked only at `c5bd55f`); rotation/purge still pending. Fail-fast added (`kumon_ems/settings.py:29-34`, `core/supabase_client.py:13-14`).
- Integrity — PARTIAL: service-role server-side only (`core/supabase_client.py:11`) but 3 admin call sites (`core/views.py:122,139`→now `:142,154`, `purge_resigned.py:35`); audit endpoint read-only (`core/views.py:357-359`, `api/urls.py:101`) yet `EmployeeAuditLog` table itself writable, no immutability.
- Authenticity — PARTIAL: `IsAuthenticated` default (`kumon_ems/settings.py:182-184`) + session login/logout with `?next=` (`core/views.py:362-377`); DRF tokens never expire, no rotation/revocation (`api/urls.py:102`); anon `dashboard-summary/` counts oracle (`core/views.py:63`).
- Accountability — PARTIAL: distinct `resigned` audit row (`core/views.py:184-188`) + purge `purged` row (`purge_resigned.py:36-39`) + signals (`core/signals.py:46-59`); no actor recorded, re-DELETE/idempotency only guarded by `icontains` check.
- Boundary — PARTIAL: credentialed CORS dev-wide, static localhost origins (`kumon_ems/settings.py:167-174`); must be env-parameterized before deploy.

## 3 Maintainability
- Modularity — PARTIAL: `api/views.py:1-3` + `api/models.py:1-3` empty stubs, all logic in `core/`; `ExpenseClaim` model+serializer (`core/models.py:116`, `core/serializers.py:129`) has no view/route (only `ClaimStatus` wired at `api/urls.py:106-110`).
- Analysability — PARTIAL: conventional commits (`git log`: `fix:`/`feat:`/`chore:`) + 47 tests green (13 `core/tests.py` + 34 `api/tests.py`); duplicate route names `dashboard`/`login` (`kumon_ems/urls.py:12-13` vs `core/urls.py:6-7`); black/isort claimed (Ch.3 Fig.8) but no config in repo.
- Modifiability — PARTIAL: pagination/versioning-safe defaults (`settings.py:185-186` PAGE_SIZE 10); no API versioning; SQLite↔Postgres parity risk (partial unique index); CASCADE scope unreviewed.
- Testability — PASS: TDD suite 47 tests (`core/tests.py:1-223`, `api/tests.py:1-603` incl. throttle/purge/audit cases at `api/tests.py:574-575`, `core/tests.py:191`); `manage.py check` clean; no coverage gate.

Top residual risks: (1) rotate 3 leaked keys + purge history; (2) expiring tokens; (3) backups + purge scheduler; (4) CORS origins per-env; (5) remove/wire `ExpenseClaim` dead code + collapse `api/` stubs.
