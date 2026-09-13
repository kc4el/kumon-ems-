# IDEAS-E — Technical / Platform Features

Scope: chore/standard-format @ 81046d1. Cap 10. Omits audit-trail export (B2 viewer covers it) and rate-limit dashboards (no rate limiting exists yet).

## E1. CI pipeline (lint + test on PR)
- Problem: no CI; PR #2 flow merges without automated checks.
- Proposal: GitHub Actions workflow on PR: ruff + `pytest` (SQLite) + migrate check; required status before merge.
- Value: every PR verified the same way, no silent breakage.
- Effort: S

## E2. Coverage gate
- Problem: 67 tests with no floor; coverage can regress unnoticed.
- Proposal: `coverage.py` in CI with `--fail-under=70`; Codecov/PR comment shows delta per PR.
- Value: locks in current coverage and ratchets it upward.
- Effort: S / Depends-On: E1 CI pipeline.

## E3. Docker packaging
- Problem: dev-only runserver; no reproducible build for staging/demo.
- Proposal: `Dockerfile` (gunicorn) + `compose.yml` (web + Postgres); `README` one-command demo up.
- Value: identical runs on reviewer laptop, staging, and prod.
- Effort: M

## E4. Staging environment
- Problem: no pre-prod; defense demo runs on dev machines.
- Proposal: staging settings module + seeded Postgres service; auto-deploy on merge to main.
- Value: safe rehearsal and review URL per release.
- Effort: M / Depends-On: E3 Docker packaging.

## E5. Healthcheck / monitoring endpoint
- Problem: no liveness signal; outages found by users, not monitors.
- Proposal: `GET /api/health/` (DB + migrations check, no auth); uptime monitor pings it every minute.
- Value: 1-minute outage detection with zero user impact.
- Effort: S

## E6. Sentry error tracking
- Problem: 500s (e.g. payroll PATCH) leave no trace beyond server log.
- Proposal: `sentry-sdk` init in prod settings with env DSN; release tag per deploy; scrub Supabase tokens.
- Value: stack trace + repro context for every prod 500.
- Effort: S / Depends-On: E4 staging (verify DSN there first).

## E7. Automated dependency updates
- Problem: Django 6.1 + DRF pinned with no update cadence; security lags.
- Proposal: Dependabot weekly for pip; CI auto-runs tests on bump PRs; major upgrades held for manual review.
- Value: patched CVEs without manual version-watching.
- Effort: S / Depends-On: E1 CI pipeline.

## E8. Backup / restore automation
- Problem: SQLite/Postgres env-switch with no backup story; one bad purge is fatal.
- Proposal: nightly `pg_dump`/file copy to versioned storage + monthly restore drill; `scripts/restore.sh` documented.
- Value: recoverable data after any purge or migration mishap.
- Effort: M

## E9. API versioning
- Problem: unversioned `/api/` breaks dashboard on every serializer change.
- Proposal: DRF namespace `v1` (`/api/v1/`), keep old routes aliased one release; changelog per breaking change.
- Value: frontend and API evolve without same-day lockstep deploys.
- Effort: M

## E10. CSV import wizards
- Problem: bulk employee/roster setup is manual entry (B1 covers export only, not import).
- Proposal: `POST /api/imports/` dry-run validate endpoint + preview-and-confirm UI; per-row error report, atomic commit.
- Value: onboarding a branch goes from hours of typing to minutes.
- Effort: M
