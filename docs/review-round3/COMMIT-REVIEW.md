# Commit Review — Round 3 Plan (8915ae4..81046d1, 13 commits)

Scope: tasks H1-H4, H6, H7a-d, S3a, S3b, S4, S5. H0/H5 correctly absent (skipped/deferred). No JWT routes added. Read-only review of diffs vs plan.

## Verdicts

- **H1 sender binding (8915ae4) — PASS.** `perform_create` uses `request.user` name, `conversation_key` defaults to `general`; serializer marks both + `attachment_url` read-only. 2 tests.
- **H2 ClaimStatus upsert (907d14e) — PASS.** ChoiceField(Pending/Approved/Rejected), blank-trim guard, atomic `select_for_update` get_or_create + custom `create` → 200 both times (plan contract kept). 4 tests.
- **H3 expense claims (55747df) — PASS.** `MinValueValidator(0.01)` + status choices, explicit serializer fields, both routes wired. Migration **0012 matches models** exactly (amount+status alters).
- **H4 apiFetch (77f627c) — PASS.** 4 raw `fetch(` → `apiFetch(`, 401→login branch above 403 (line 39). Remaining `fetch(` are the helper itself, session-login, and anon signup (intentional).
- **H6 onboarding+signup (4928106) — PASS with noted deviation.** Password validated pre-Supabase (weak→400), lazy `User` import, `session-login` round-trip asserted, signup posts `/api/employees/` with names, help text added. 3 tests + weak-pw.
- **H7a attendance (4023ce3) — PASS.** Live `apiFetch`, empty-state row, demo fallback + toast, `setApiMode`.
- **H7b shifts (9178fd2) — PASS.** Same pattern + per-row ⚠ conflict badge via `shift-rosters/conflicts/`.
- **H7c payroll (a49f9b1) — PASS.** Runs + items live, empty-state, mode/toast pattern.
- **H7d audit+offboarding (be5327a) — PASS.** Audit live; offboarding resolves by email → DELETE resign flow (no new endpoint needed, as plan allowed).
- **S3a notifications (e3ab8c9) — PASS.** Model/serializer/views/routes per plan; leave + shift `post_save` hooks. Migration **0013 matches model** (incl. ordering).
- **S3b conflicts (3194acc) — PASS.** `ShiftConflictView` exact per plan; route placed before `<uuid:pk>`; 400 on missing params. 2 tests.
- **S4 checklist — PASS (no commit, per plan).** No "Live allocation/Confirmed" strings; loading→rows/empty→toast present on all live views; `?next=` bounce covered by H4 branch. Manual matrix belongs in PR body.
- **S5 purge (81046d1) — PASS.** `IsAdminUser`, `days=int()`→400 on garbage, dry-run default True, response adds `would_purge`/`purged` counts (additive, test-needed). 4 tests.

## Flagged deviation: H6 AllowAny on POST /api/employees/

**Necessary: yes** — logged-out signup cannot pass `IsAuthenticated`. **Safety: acceptable with caveats.** Mitigations verified: `AnonRateThrottle` 100/day active (settings + throttle test), GET still authed, password validated before any Supabase/Django write (no orphan on weak pw), no staff flag granted. Residual: anonymous employee+User creation (spam/enumeration) — inherent to self-service signup; recommend CAPTCHA or approval queue as follow-up, not a blocker.

## Overall: PASS

All 13 plan items implemented as specified; no item dropped; migrations match models; deviations necessary, safe, and additive. 20 new tests found in diff (54 total in file). Not re-running suite here (runner: 67/67 green).
