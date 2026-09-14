# Round-2 Compiled Review — chore/standard-format @ c8690ed (2026-09-10)
Scope: synthesis only of `docs/review-round2/01–05.md` (security / correctness / API / frontend-UX / SOP+Ch.3); no new auditing, code changes, or re-verification. ID legend: S=01-security, C=02-correctness, A=03-api-design, F=04-frontend-ux, P=05-sop-coverage.
## Top-12 deduped findings (ranked)
1. [CRITICAL] Live secrets in git history (`597d245` `.env`: SECRET_KEY+SERVICE_ROLE+DB_PASSWORD; fail-fast `kumon_ems/settings.py:29-34` only stops fallback) — rotate 3 keys + purge history — (S1).
2. [CRITICAL] Auth lifecycle broken end-to-end: non-expiring DRF tokens, no throttle/logout (`api/urls.py:98`, `kumon_ems/settings.py:161-171`) + JS sends no `Authorization`/CSRF so writes 403 (`static/js/dashboard.js:258,601,952,983`) + login/signup mock (`dashboard.js:760-818`, `login.html:44,51`) + 403 no `?next=`, summary swallows 403 (`dashboard.js:264,613,985,952-956`) — (S2,S3,F3,F6,A10).
3. [HIGH] Purge fail-open + destructive + manual-only: deletes local row on Supabase error (`core/management/commands/purge_resigned.py:29-33`), CASCADE wipes payroll/attendance (`core/models.py:43,57,88,99`), no audit/floor/confirm/txn, day-30 boundary + negative `--days` unvalidated, no scheduler/UI trigger — (S5,C2,C8,C12,P5).
4. [HIGH] Concurrency guards validate-only → races/wrong codes: shift overlap no constraint/atomic (`core/serializers.py:85-99`), employee dup race → 502 via broad `except` (`core/views.py:114,136`) + dead `record_id` (`:121`) + `user=None` orphan, attendance PUT unguarded → 500 (`serializers.py:44`, `views.py:165-170`), clock-out `select_for_update` no-op on SQLite + count/first re-query (`views.py:200-203) — (C1,C4,C6,C9,A1,A2).
5. [HIGH] Payroll PATCH without `base_pay` → KeyError 500 (`core/views.py:276,291-292`); payroll manually posted, never derived from attendance — (C3,P2).
6. [HIGH] Demo-fallback confusion: fetch failures silently keep demo values, no offline/badge (`dashboard.js:970-972,1022-1024`); fake "Live allocation" (`:336-340`) + "Confirmed" badge with no POST (`:424-429`) — (F1,F2).
7. [MED] Contract incoherent: 3 error shapes `{error}`/`{detail}`/`{non_field_errors}` (`core/views.py:82,106,116,146,183,191,208,213,219,230`, `core/exceptions.py:4-7`, `api/urls.py:98`, no `EXCEPTION_HANDLER`) + 400/409 split per path (attendance/shift/payroll/email) + soft-delete returns 204-empty yet GETs 200 (`core/views.py:155-158`) — (A1,A2,A3,A6,C6).
8. [MED] Soft-delete audit gap + clock reset: only generic "updated" signal, no actor/resigned marker (`core/views.py:155-158`, `core/signals.py:47-57`); re-DELETE restarts `resigned_at`, bulk deletes bypass → hard delete — (S6,C7).
9. [MED] Service-role blast radius 1→3 (create `core/views.py:122`, rollback `:139`, purge `purge_resigned.py:30`), server-side only (`core/supabase_client.py:11`) but any view/SSRF bug inherits god-mode — (S4,C4).
10. [MED] Frontend mostly static + weak validation + XSS gap: shifts/attendance/claims/advance/inbox/audit/offboarding/payroll toast-only or hardcoded (`dashboard.js:520-554,568-573,650-716,861-920,217-220,289-294`, `index.html:145-200,1114,1170,3698-3700`), HTML-only validation + naive name split + no end<start (`index.html:3732-3881`, `dashboard.js:250-257`), unescaped `innerHTML` in `confirmAddStaff` (`:411-420`; `escapeHtml :718-720` covers rest), no spinners/empty-state/double-submit guard — (F11,F9,F10,F4,F5).
11. [MED] Deploy/docs gaps: credentialed CORS dev-wide (`kumon_ems/settings.py:151-158`), anon `dashboard-summary` counts oracle (`core/views.py:55`), `auth-token`+403 rule undocumented (`README.md:7-14`), no `page_size`/filter, `DepartmentList` unordered (`core/views.py:87-89`), no versioning — (S7,S8,A4,A5,A10,A11).
12. [LOW] Edge-case residue: naive `clock_out` assumed UTC + `==` accepted + date-vs-`Attendance.date` unchecked (`core/views.py:194-195,217`); NULL work_date/employee skips overlap, overnight unrepresentable (`serializers.py:85-87`); mig 0004 no data migration; route-order/naming/redirect-dup; modal/toast inconsistencies (`api/urls.py:45-54`, `kumon_ems/urls.py:14-15`, `core/urls.py:8-9`, `main.css:1507,1998`, `dashboard.js:223-244,558-584,926-947`) — (C10,C11,C13,A7,A8,A9,F7,F8,F12).
## SOP re-grade (Ch.1 numbering)
| SOP | Verdict | Evidence |
|---|---|---|
| S1 dashboard | COVERED | `DashboardSummaryView` (`core/views.py:51`, `api/urls.py:28`) + live summary/directory/onboard/leave fetches (`dashboard.js:952,983,258,601`) |
| S2 attendance+payroll | COVERED | `unique_together` (`models.py:49`) + dup/race/clock-out guards (`serializers.py:44-49`, `views.py:165-210`); payroll persisted per period, never auto-derived |
| S3 shifts+notifications | PARTIAL | Scheduling fixed (FK+`work_date` `models.py:66-69`, overlap `serializers.py:75-100`); notifications MISSING (zero model/endpoint/client code) |
| S4 safety+UX | PARTIAL | Safety covered (server-side Supabase+rollback, token endpoint, `IsAuthenticated`, audit+`audit-logs/`); UX partial (only dashboard/employees/leaves live) |
| S5 resignation+30d delete | PARTIAL | Soft-resign on DELETE + `purge_resigned --days 30 --dry-run` (`views.py:155-158`, `purge_resigned.py:13-34`, `core/tests.py:114-153`); no scheduler/UI — manual only |
## Chapter-3 corrections (`docs/chapter3/CHAPTER3.md`)
- §3.4.5 "erasure via `DELETE employees/<uuid:pk>/`" FALSE: endpoint soft-deactivates (`views.py:155-158`); erasure is `purge_resigned`, never named.
- §3.4.5 "window enforced as retention policy" OVERSTATED: purge exists but UNSCHEDULED (no cron/Celery) — deletion is not automatic.
- §3.4.2 flowchart "422 ValidationError" WRONG: dup → 400 fast-path / 409 race (`views.py:169-170`, `exceptions.py:7`); "airtight" overstates — payroll never derived from attendance.
- §3.4.3 "roster adjusted for absence" OVERSTATED: no leave→roster link; manual side-by-side CRUD only.
- §3.4.4 "tamper-evident history" OVERSTATED: `EmployeeAuditLog` is a plain writable table, no immutability.
- MISSING: token auth + `IsAuthenticated` + public-summary exception (§§3.2/3.4.4); shift-overlap validator (§3.4.3); `purge_resigned` + unscheduled status (§3.4.5); SOP3 notifications gap; frontend wiring state (live vs static views).
## Recommended fix order
1. Rotate leaked keys + purge/squash history (human job, finding 1).
2. Fix auth end-to-end: token expiry/throttle + one scheme (session+CSRF or token header) wired into JS + real login/logout + `?next=` (finding 2).
3. Make purge safe: fail-closed, audit rows, `--days` floor/confirm, per-employee txn, preserve payroll history or scope CASCADE (finding 3).
4. Close concurrency holes: atomic creates, DB constraints (shift overlap, open-attendance), correct 409/500 paths (finding 4).
5. Fix payroll PATCH KeyError + decide attendance→payroll derivation policy (finding 5).
6. End demo-confusion: offline/demo badges, fail-loud, drop fake "Live/Confirmed" labels (finding 6).
7. Unify contract: one error envelope, one 409 rule, honest soft-delete status (finding 7).
8. Distinct soft-delete audit action + idempotent re-DELETE + guard bulk deletes (finding 8).
