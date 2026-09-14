# ISO/IEC 25010 — Justification & Improvements

Scope: `chore/standard-format` @ `cf89b71`. Source verdicts: `docs/iso25010/01–03`.
Rule used below: a PARTIAL/FAIL is **justified** when it follows from the project's
stated academic scope (single-node pilot, graded manuscript, fixed SOPs); everything
else gets a concrete improvement with priority (P0 = before defense, P1 = before
production, P2 = nice-to-have).

## P0 — before defense

| # | Finding (source) | Justification | Improvement |
|---|---|---|---|
| 1 | Confidentiality FAIL — live keys in git history `597d245` (02) | None. Unjustifiable in any scope. | Human job: rotate SECRET_KEY + SERVICE_ROLE + DB_PASSWORD in Supabase dashboard and local `.env`; record rotation in PR #2 body. History rewrite explicitly out of scope (would break teammates' clones). |
| 2 | Signup still toast-only mock (03) | None — a fake signup on a graded portal misrepresents the system. | Wire the signup form to the real onboarding path (`POST /api/employees/` via session) or remove the tab and keep login-only; re-check `dashboard.js:963-990`. |
| 3 | Accessibility FAIL — zero ARIA/live regions (03) | Partially justified (no disabled-user requirement in SOPs), but toasts already exist so the fix is cheap. | Add `role="status"` to the toast container + `aria-live="polite"`; add skip-link and labels on the login form. Half a day. |

## P1 — before any production use

| # | Finding (source) | Justification | Improvement |
|---|---|---|---|
| 4 | Tokens never expire, no revocation (02) | Justified for the pilot: one operator, throttled API, logout deletes the token. | Migrate to SimpleJWT with short access + rotating refresh tokens; document the token story in README. |
| 5 | No backups, purge manual-only, CASCADE wipes payroll (01, 02) | Justified for SQLite pilot (file copy = backup); NOT justified on Postgres. | Nightly `pg_dump` + weekly `purge_resigned` schedule (cron/Task Scheduler line is already in README); decide anonymize-vs-delete for payroll history before enabling CASCADE purges on real data. |
| 6 | CORS credentialed dev-wide, static origins (02) | Justified locally; blocks deploy. | Parameterize `CORS_ALLOWED_ORIGINS` per environment (prod block already exists in settings — extend it). |
| 7 | App cannot boot without Supabase keys even on SQLite (03) | Partially justified (auth is core to SOP4); makes every fresh clone fail at first `migrate`. | Lazy-load the Supabase client (create on first use, not import); add `.env.example` so setup is copy-paste. |
| 8 | DB swappable, auth provider hard-wired (03) | Justified: SOPs name Supabase; an auth abstraction layer is YAGNI for one provider. | No code — record the decision in README so the panel sees it was deliberate. |
| 9 | Overlap/clock-out guards validate-only, no DB constraint for shifts (01, 02) | Justified on SQLite (partial unique index already covers open attendance; true exclusion constraints need Postgres). | On Postgres: add `ExclusionConstraint` for shift overlap; keep app-level guard as the error-message path. |
| 10 | 5× `count()` dashboard summary, no caching (01) | Justified at pilot scale (tiny tables, 10/page). | Single aggregate query or 60s cache when headcount grows; add `select_related` on directory/attendance lists first (cheapest win). |

## P2 — nice-to-have

| # | Finding (source) | Justification | Improvement |
|---|---|---|---|
| 11 | ExpenseClaim dead code, empty `api/` stubs, duplicate route names (02) | Justified as merge residue from upstream; harmless at runtime. | Wire or delete `ExpenseClaim` routes; collapse `api/` stubs into `core/` or document the split; dedupe `dashboard`/`login` route names. |
| 12 | README pip line omits driver/versions, unix-only activate (03) | Docs-only. | One-line README fix + `.env.example` (shared with #7). |
| 13 | No i18n, modal/Escape inconsistencies, no double-submit guard (03) | Justified: single-language panel demo; cosmetic. | `role="status"` covers the worst (see #3); rest only if time permits. |
| 14 | Payroll manual-post, leave↔roster unlinked, notifications missing (01) | Justified: product decisions the SOPs never specify — not bugs. | Only with adviser sign-off; each needs a policy (overtime rules, retention vs anonymization, who gets notified) before code. |

## Deliberately not fixing

- **Sh
...[truncated] 785 chars]