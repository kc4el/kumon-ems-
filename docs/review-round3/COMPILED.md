# Review Round 3 — COMPILED (all angles, deduped)

Date: 2026-09-11 · Branch: chore/standard-format · HEAD: cf89b71
Scope: synthesis of round-3 reviews 01–08 at cf89b71 (no new audit, no code changes, no test runs).
Sources: 01-security · 02-correctness · 03-api-design · 04-frontend-ux · 05-sop-coverage · 06-functionality · 07-performance · 08-test-coverage.
Adjudication: full Django suite = 47 tests (13 core + 34 api, multiple green runs) — 05's "fix to 13" claim is NOT a chapter error and is excluded below.

## Top-25 deduped findings (by discovering angle; severity-ranked within each; prior Top-15 items kept, 10 new marked ★)

### 01 Security
1. [CRITICAL] Live secrets in git history (commit 597d245: SECRET_KEY+SERVICE_ROLE+DB_PASSWORD) — rotation + purge still PENDING (.env:1) (01)
2. [HIGH] ClaimStatus POST upsert-blind — ignores validated_data, raw request.data, None-claim_id collapse, no atomicity, free-text status, race→500 (core/views.py:406-412) (01+02+03)
3. [HIGH] Message sender client-supplied + demo defaults persist — any authed user posts as anyone into any conversation (core/views.py:395-399) (01+02)
4. [HIGH] DRF tokens never expire, no rotation — leaked token valid forever; logout deletes only as side effect (api/urls.py:102) (01+08)
5. [MED] Onboarding provisions no Django login — Supabase Auth user + Employee row only; SessionLoginView reads User table (core/views.py:127-143) (01)
6. [MED] Throttle anon 100/day + user 1000/day too coarse — batch day exceeds it; AllowAny polling behind one NAT burns anon quota (kumon_ems/settings.py:191) (01+07)
7. [LOW] No brute-force protection on credential endpoints beyond global anon throttle — no lockout or scoped rate (api/urls.py:102-104) (01) ★

### 02 Correctness
8. [HIGH] ExpenseClaim views orphaned — model+serializer+list/detail views exist but zero routes, clients hit 404 (core/views.py:415-422) (02+03+06)
9. [MED] ClaimStatus.claim_id free text, no FK to ExpenseClaim.id — typos/UUID mismatch orphan rows, dual status sources disagree (core/models.py:150) (02)
10. [MED] ExpenseClaim no domain guards — negative/zero amount, free-text status, fields="__all__" allows employee reassignment post-approval (core/models.py:116-125) (02)
11. [MED] Message.validate KeyErrors off-request — indexes self.context["request"] directly; shell/signal/test use raises KeyError, not ValidationError (core/serializers.py:165-170) (02) ★
12. [MED] Message.attachment unbounded — FileField with no validators, no FILE_UPLOAD_MAX/DATA_UPLOAD_MAX set; attachment URL built with no storage-exists guard (core/models.py:140-142) (02) ★

### 03 API Design
13. [LOW] Error envelope hole — hand-rolled Response({"error": exc.detail}) bypasses handler, nested-dict vs flat-string shape (core/views.py:121) (03)
14. [LOW] No filter/search/OrderingFilter on any list, no page_size param; no /api/v1/ versioning; auth-token + 403-for-anon undocumented (api/urls.py:30-111) (03) ★

### 04 Frontend/UX
15. [HIGH] Claims/messages bypass apiFetch — raw fetch, no CSRF/credentials/403→login/badge; writes risk 403 (static/js/dashboard.js:581,592,806,871) (04+06)
16. [MED] Signup mock reports success without creating anything, adjacent to real login (static/js/dashboard.js:963-990) (04+06)
17. [MED] apiFetch handles only 403 — 401/419 pass through silently, no re-auth redirect (static/js/dashboard.js:29) (04) ★

### 05 SOP/Paper
18. [MED] Residual SOP gaps — payroll manually posted, never derived from attendance; purge has no scheduler/UI trigger and CASCADE wipes attendance/payroll/leaves on hard purge (core/views.py:170-199) (05) ★

### 06 Functionality
19. [MED] Clock-in/out, shifts, payroll views, audit, offboarding all MOCK — toast/DOM-only, never hit their routed endpoints (static/js/dashboard.js:251,321,418,643,1023) (06) ★

### 07 Performance
20. [MED] Prod serving story missing — static via Django insecure=True, runserver only, no PG pooling (fresh TCP+TLS per request) (kumon_ems/urls.py:24) (07)
21. [MED] SQLite default serialises writes; select_for_update() at clock-out is a documented no-op until Postgres (kumon_ems/settings.py:107-114) (07) ★
22. [MED] No bulk endpoints — onboarding 100 staff / a payroll run = 100+ POSTs; PAGE_SIZE fixed at 10 (kumon_ems/settings.py:185-186) (07) ★

### 08 Test Coverage
23. [MED] messages/, claim-statuses/, ExpenseClaim: 0 tests; all detail-route mutations + clock-out 200/404/409 + payroll PATCH variants untested (08)
24. [MED] No coverage gate/CI, no JS tests (~1000-line dashboard.js), no e2e, no throttle/429 test (08)
25. [MED] Dishonest race test — test_attendance_race_maps_to_409 patches transaction.atomic and never touches DB/serializer; model IntegrityError tests skip API 404/409 branches (08) ★

## SOP re-grade (from 05, re-verified against code)

| SOP | Verdict | Evidence |
|---|---|---|
| S1 centralized dashboard | COVERED | DashboardSummaryView (views.py:59-92) + six live regions in dashboard.js |
| S2 attendance + payroll | COVERED | unique_together + partial-unique guard, 409 fast-path, server-computed net_pay |
| S3 shifts + notifications | PARTIAL | Scheduling covered; notifications = inbox Message only, no shift/leave link |
| S4 safety + UX | PARTIAL | Validate-first + rollback + auth covered; attendance/shifts/payroll/audit static |
| S5 resignation + 30d delete | PARTIAL | Soft-delete + fail-closed purge + audit covered; no scheduler/UI, CASCADE wipes on purge |

## Chapter-3 corrections (docs/chapter3/CHAPTER3.md)

- §3.4.4 flowchart (ll.114-118) + text l.110 STALE — shows Auth-user-create-before-validate; code validates locally first (views.py:117-126) then creates Auth user (:128-144). Fix order. (05, legitimate — kept)
- Fig.8 "47 tests" caption — VERIFIED TRUE per adjudication (13 core + 34 api); NO change, excluded from error list. (05 claim set aside)
- All other §3.1–§3.4 claims verified TRUE, no change: six live regions (§3.4.1), Figs 7–8 refs, DB-switch row, UNDER DEVELOPMENT rule, 422→409 fix, manual-link honesty, soft-delete honesty. (05)

## Recommended fix order (8 steps)

1. Rotate + purge leaked secrets from history (finding 1) — prod blocker, do first.
2. Bind message sender to request.user; make sender_name read-only; drop demo defaults (4).
3. Fix ClaimStatus write path: validate, FK/choices, atomic upsert, PUT-on-claim_id or 200-vs-201 (3, 9).
4. Wire or delete ExpenseClaim routes + add domain guards (2, 10).
5. Route claims/messages through apiFetch (CSRF/credentials/403→login); wire or remove signup (6, 8).
6. Token expiry/rotation + provision Django user at onboarding or document operator-only auth (5, 7).
7. Add missing API tests (messages/claims/clock-out/detail routes) + coverage gate ≥80% + one JS smoke test (11, 12).
8. Prod hardening: WSGI server + static story + PG pooling, then scoped throttles, bulk import, indexes (13, 14, 15).
