# Review Round 3 — SOLUTIONS DRAFT (planning only, no code changes)

Scope: `chore/standard-format` @ `cf89b71` · Inputs: `COMPILED.md` Top-15, `IDEAS-A-sop-gaps.md` (5), `IDEAS-B-enhancements.md` (8), `JUSTIFICATION-AND-IMPROVEMENTS.md` (P0/P1/P2 — no new scheme invented).

## Part 1 — Fixes for compiled Top-15

### F1. Live secrets in git history [CRITICAL]
- Problem: SECRET_KEY + SERVICE_ROLE + DB_PASSWORD committed in history are still valid.
- Root cause: live values committed and never rotated (`597d245`, see `.env:1`).
- Fix: (a) ★ Rotate all three keys in Supabase dashboard + fresh local `.env`, record rotation in PR body — kills exploitability without breaking teammates' clones. (b) Rewrite history with git-filter-repo — rejected, breaks every clone (out of scope per Justification P0 #1).
- Effort: S · Test: `api/tests.py::test_settings_secret_key_is_not_committed_value` · Skip-risk: full production compromise on a leaked key.

### F2. ExpenseClaim views orphaned — zero routes [HIGH]
- Problem: model + serializer + list/detail views exist but no URL route, so clients get 404.
- Root cause: views added without URL wiring (`core/views.py:415`).
- Fix: (a) ★ Wire `CRUD /api/expense-claims/` + approve/reject actions — reuses existing view code, smallest diff. (b) Delete model + views + stubs entirely.
- Effort: S · Test: `api/tests.py::test_expense_claim_list_returns_200` · Skip-risk: claims feature unusable; panel demos a dead flow.

### F3. ClaimStatus POST upsert-blind [HIGH]
- Problem: write path ignores validated_data, collapses on None claim_id, no atomicity, race → 500.
- Root cause: raw `request.data` write without serializer/FK/transaction (`core/views.py:406`).
- Fix: (a) ★ Serializer-validated atomic `update_or_create` on FK + status choices — kills the 500, the race, and free-text drift in one path. (b) Split into PUT-on-claim_id endpoint with 200-vs-201 semantics.
- Effort: M · Test: `api/tests.py::test_claim_status_concurrent_upsert_writes_single_row` · Skip-risk: duplicate/orphan status rows and 500s under concurrent review.

### F4. Message sender client-supplied + demo defaults [HIGH]
- Problem: any authenticated user can post as anyone into any conversation.
- Root cause: sender taken from request body with demo fallback (`core/views.py:395`).
- Fix: (a) ★ Bind sender to `request.user`, make sender_name read-only, drop demo defaults — closes impersonation at the trust boundary. (b) Allowlisted operator override for data imports.
- Effort: S · Test: `api/tests.py::test_message_sender_ignores_client_supplied_value` · Skip-risk: impersonation and fraudulent audit trail.

### F5. DRF tokens never expire, no rotation [HIGH]
- Problem: a leaked token is valid forever; logout deletes it only as a side effect.
- Root cause: non-expiring authtoken obtain endpoint (`api/urls.py:102`).
- Fix: (a) ★ Migrate to SimpleJWT with short-lived access + rotating refresh — standard path, matches scheduled P1 #4. (b) Custom expiry + manual revocation list on current tokens.
- Effort: M · Test: `api/tests.py::test_expired_access_token_returns_401` · Skip-risk: one leaked token means permanent account takeover.

### F6. Claims/messages bypass apiFetch [HIGH]
- Problem: raw fetch calls skip CSRF/credentials and 403→login handling, so writes risk silent 403.
- Root cause: hand-rolled fetch in dashboard claims/messages paths (`static/js/dashboard.js:581`).
- Fix: (a) ★ Route all claims/messages calls through `apiFetch` — one CSRF/403→login path instead of per-call patches. (b) Add CSRF headers per call site.
- Effort: S · Test: `static/js/tests/apiFetch.test.js::test_claims_write_redirects_to_login_on_403` · Skip-risk: writes fail silently and unread badges go stale.

### F7. Onboarding provisions no Django login [MED]
- Problem: onboarding creates Supabase Auth user + Employee row only, so SessionLoginView finds no User.
- Root cause: no Django User creation in onboarding transaction (`core/views.py:127`).
- Fix: (a) ★ Create the Django User in the same transaction as the Employee row — makes login work for every onboarded hire. (b) Document operator-only auth and keep Supabase-only login.
- Effort: S · Test: `core/tests.py::test_onboarding_creates_django_user` · Skip-risk: newly onboarded staff cannot log in.

### F8. Signup mock reports success without creating anything [MED]
- Problem: fake signup success sits next to real login and misrepresents the system.
- Root cause: toast-only mock handler never posts to any endpoint (`static/js/dashboard.js:963`).
- Fix: (a) ★ Wire the form to the real onboarding path (`POST /api/employees/`) — a fake signup on a graded portal is unjustifiable (P0 #2). (b) Remove the tab and keep login-only.
- Effort: S · Test: `static/js/tests/signup.test.js::test_signup_posts_to_onboarding_endpoint` · Skip-risk: graded demo shows fabricated success, an integrity failure.

### F9. ClaimStatus.claim_id free text, no FK [MED]
- Problem: typos/UUID mismatches orphan rows and the two status sources disagree.
- Root cause: plain text field instead of FK to ExpenseClaim (`core/models.py:150`).
- Fix: (a) ★ FK to `ExpenseClaim.id` with data migration — the database enforces the link permanently. (b) UUID-format validation only, no FK.
- Effort: M · Test: `core/tests.py::test_claim_status_rejects_unknown_claim_id` · Skip-risk: orphan status rows and conflicting claim states.

### F10. ExpenseClaim has no domain guards [MED]
- Problem: negative/zero amounts, free-text status, and `fields="__all__"` allow post-approval employee reassignment.
- Root cause: unconstrained model fields and permissive serializer (`core/models.py:116`).
- Fix: (a) ★ Validators (amount > 0, status choices) + read-only employee on the serializer — cheapest, no migration. (b) DB-level CHECK constraints.
- Effort: S · Test: `core/tests.py::test_expense_claim_rejects_negative_amount` · Skip-risk: negative payouts and tampering with approved claims.

### F11. messages/, claim-statuses/, ExpenseClaim: 0 tests [MED]
- Problem: all detail-route mutations, clock-out 200/404/409 paths, and payroll PATCH variants are untested.
- Root cause: coverage gap — no tests exist for these paths (`api/tests.py:1`, by absence).
- Fix: (a) ★ Add API tests for messages/claims/clock-out/detail mutations first — covers the HIGH fix paths above. (b) Full coverage sweep of every endpoint.
- Effort: M · Test: `api/tests.py::test_clock_out_twice_returns_409` · Skip-risk: regressions in the HIGH-severity paths ship unseen.

### F12. No coverage gate/CI, no JS tests [MED]
- Problem: ~1000-line dashboard.js, no e2e, no throttle/429 test, and nothing enforces coverage.
- Root cause: CI pipeline config missing (repo root, `.github/workflows/ci.yml:1`, by absence).
- Fix: (a) ★ CI running pytest with ≥80% gate + one JS smoke test — blocks regressions at PR time. (b) Local-only coverage script with no enforcement.
- Effort: M · Test: `static/js/tests/smoke.test.js::test_dashboard_renders_summary_regions` · Skip-risk: coverage rots and frontend regressions stay invisible.

### F13. Anon 100/day + user 1000/day throttles too coarse [MED]
- Problem: batch day exceeds the limit and AllowAny polling behind one NAT burns the anon quota.
- Root cause: single global throttle classes (`kumon_ems/settings.py:191`).
- Fix: (a) ★ Scoped rates per view (burst + sustained, higher for batch import) — unblocks batch day without opening an anon flood. (b) Raise the global limits.
- Effort: S · Test: `api/tests.py::test_batch_import_within_scoped_throttle` · Skip-risk: legitimate batch imports get 429s; shared-NAT users lock each other out.

### F14. Production serving story missing [MED]
- Problem: static served via Django `insecure=True` with runserver only and no PG pooling.
- Root cause: dev-only serving left as the default (`kumon_ems/urls.py:24`).
- Fix: (a) ★ Gunicorn + WhiteNoise/S3 static + `CONN_MAX_AGE`/pgbouncer — smallest production-grade story on the current stack. (b) Full container + reverse-proxy deploy.
- Effort: L · Test: `core/tests.py::test_prod_settings_disallow_insecure_static` · Skip-risk: insecure static serving and per-request TCP+TLS latency under load.

### F15. Error envelope hole [LOW]
- Problem: hand-rolled `Response({"error": exc.detail})` bypasses the handler; nested-dict vs flat-string shapes.
- Root cause: per-view error construction instead of a global handler (`core/views.py:121`).
- Fix: (a) ★ Single DRF `exception_handler` producing one flat envelope — fixes every view at once. (b) Patch each view individually.
- Effort: S · Test: `api/tests.py::test_error_envelope_is_flat_string` · Skip-risk: clients parse two error shapes and mishandle failures silently.

## Part 2 — Feature ranking (all 13 proposals from IDEAS-A + IDEAS-B)

| Rank | Proposal | Value | Effort | Depends-On | SOP link |
|---|---|---|---|---|---|
| 1 | A5 ExpenseClaim wiring (or delete) — scheduled P2 #11 | H | S | none | S4-UX |
| 2 | A1 Leave→Roster auto-block — scheduled P2 #14 | H | S | none | S3-scheduling |
| 3 | A4 Purge scheduler + confirm UI — scheduled P1 #5 | H | M | none | S5 |
| 4 | B8 Dashboard cached summary — scheduled P1 #10 | M | S | none | enhancement |
| 5 | A2 SOP3 notifications — scheduled P2 #14 | H | M | none | S3-notifications |
| 6 | B5 Attendance correction requests | M | S | none | enhancement |
| 7 | B2 Audit-log dashboard | M | S | none | enhancement |
| 8 | A3 Attendance→Payroll derivation — scheduled P2 #14, blocked on adviser decision | H | M | none | S2-payroll |
| 9 | B1 Payroll/attendance CSV export | M | S | none | enhancement |
| 10 | B7 Employee profiles + avatars | M | S | none | enhancement |
| 11 | B3 Role-scoped views | M | M | B7 | enhancement |
| 12 | B6 Password reset (adjacent to scheduled P1 #4 token lifecycle) | M | M | A2 | enhancement |
| 13 | B4 Shift-swap request flow | L | M | A1 | enhancement |

Top 5 for the next build: A5 (unblocks HIGH claims fixes F2/F3/F9 at S effort); A1 (S effort, flips a false S3 roster claim to COVERED); A4 (only P1-scheduled path from manual-only to automatic S5); B8 (S effort P1, kills the demo-confusion fallback and summary latency); A2 (last MISSING→COVERED SOP slice; A3 deferred until the payroll policy decision lands).

## Adviser decisions needed (code must not guess)

- Payroll derivation policy (overtime/base-pay rules — PATCH-without-base_pay 500s the gap): blocks A3.
- Notification audience + channel (inbox-only vs email, who gets leave/shift decisions): blocks A2 design.
- Purge retention rule (anonymize vs delete payroll history before CASCADE purges on real data): blocks A4 enablement.
