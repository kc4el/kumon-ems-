# 07 — API contract residuals (written by lead; two agent attempts died pre-write, probes harvested from trail)

Probe evidence (re-verified from `deleg_722d7cfa/task-6.log` trail, 2026-09-13):
- P1 dept PUT duplicate name → 400 `{"error": ...}` (handled, fine).
- P2 employee PATCH duplicate email (exact case) → 400 `{"error": ...}` (handled, fine).
- P3 leave-allocation PUT duplicate unique-together → **500 non-JSON HTML** (`IntegrityError: UNIQUE constraint failed: core_leaveallocation.employee_id, ...`). Real, unhandled.

## Issues

1. **HIGH — Allocation PUT/PATCH duplicate → 500 HTML.** `PUT /api/leave-allocations/<id>/` colliding `(employee, leave_type, year)` raises raw `IntegrityError`; no guard, non-JSON body breaks `apiFetch` JSON parse. Repro: create two allocations, PUT one onto the other's triple → 500. Fix: catch `IntegrityError → 409` in the allocation view (same pattern as T7's OT guard). Source: probe P3.
2. **HIGH — `auth-token/` unthrottled + login exempt (carried, still open).** DRF `ObtainAuthToken.throttle_classes == ()`; session-login `== []`. Unlimited credential guessing. Fix: scoped burst throttle per plan batch. Source: `01-auth-sessions.md` bug 3.
3. **MED — `?next=` open redirect (carried, still open).** `/login/?next=https://evil/` navigates off-site post-login (`dashboard.js:1284-1285`). Fix: same-origin `^/(?!/)` check. Source: round-5 #15.
4. **MED — Conversation-key default mismatch (carried, still open).** POST lands in `"general"`, bare GET reads `"sarah"` → messages invisible. Fix: single constant. Source: round-5 #19.
5. **MED — Chat uploads unvalidated (carried, still open).** Any MIME/size to guessable `/media/` path; 404 when DEBUG off. Fix: allowlist + random names. Source: round-5 #20.
6. **MED — Bad-UUID/date params → 500 family (carried, still open).** `conflicts/?employee=xxx`, malformed dates, negative purge `days` → unhandled `ValidationError`/`CommandError` → 500. Fix: catch → 400. Source: round-5 #12 (partially; employee PATCH exact-case now 400 per P2).
7. **LOW — Envelope/status nits (carried).** `{message}` success trio vs `{error}`; claim-status POST 200-on-create; employee DELETE 200-not-204; flattened field errors. Documented tradeoffs, no behavior fix. Source: round-5 dropped-contract section.
8. **LOW — Untested routes.** 7 detail routes (department, attendance, leave-allocation, shift-roster, payroll-run, performance, expense-claim) + no PUT/non-employee-DELETE coverage + untested 429 path. Coverage work, no user-facing bug. Source: round-5 `07-api-design.md` missing section.
