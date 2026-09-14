# 07 — Performance & Scalability (round 3, @ cf89b71)

Scope: fresh audit of query shape, pagination, throttles, DB, static/serving. Round-2 settled items (missing throttle/pagination/exception-handler) verified FIXED — not repeated.

## Findings

1. [LOW] `DashboardSummaryView` fires 5× `COUNT(*)` per GET — `core/views.py:67-75`. Tables are tiny so each count is ~ms; no N+1, no join. Fix when headcount grows: single aggregate or 60s low-cache (public endpoint, `AllowAny` `:63`).
2. [LOW] Zero `select_related`/`prefetch_related` anywhere — `core/views.py:95-422`, `core/serializers.py:20-151`. No N+1 TODAY (FK serializers emit PKs only, no nested reads), so this is latent, not active. First wins when nesting is added: `Attendance/Leave/Shift/PayrollItem/ExpenseClaim.employee`, `Employee.department`, `PayrollItem.payroll_run` (join-ordered at `core/views.py:314-316`).
3. [LOW] Clock-out costs 2 reads (`count()` then `first()`) — `core/views.py:253-264`. One `SELECT … LIMIT 2` suffices (0/1/>1 distinction preserved).
4. [LOW] Per-write extra reads by design: email `exists()` `core/views.py:122`, attendance dup `exists()` `core/serializers.py:53-56`, shift clash `exists()` `core/serializers.py:94-102`. Correctness-positive, negligible at pilot volume.
5. [MED] Pagination now covers ALL lists (global `PageNumberPagination`, `PAGE_SIZE 10` — `kumon_ems/settings.py:185-186`; stale `pagination_class=None` gone). No `PAGE_SIZE_PARAM`, so clients can't blow up pages — good. But no bulk endpoints either: onboarding 100 staff / posting a payroll run = 100+ POSTs.
6. [MED] Throttle `anon 100/day, user 1000/day` (`kumon_ems/settings.py:191`) cuts both ways: stops abuse, but a legit batch day (onboarding + attendance + payroll lines) exceeds 1000 writes/user; `AllowAny` summary + directory polling behind one NAT IP can burn the anon 100/day. Recommend scoped rates (e.g. burst on `auth-token/`, looser authed writes or a bulk import path).
7. [MED] SQLite default (`kumon_ems/settings.py:107-114`) serialises writes (single-writer lock) — fine for pilot, risky at roster/clock-in peaks. `select_for_update()` at `core/views.py:249` is a documented no-op on SQLite; real locking only arrives with Postgres. Partial-unique `one_open_attendance_per_employee` (`core/models.py:53-58`, mig `0010`) is the true guard.
8. [MED] Postgres path exists (`DB_HOST` → psycopg2, `kumon_ems/settings.py:95-106`, `requirements.txt:6`) but no pooling: no `CONN_MAX_AGE`, no PgBouncer/Supabase-pooler note. Each request opens a fresh TCP+TLS connection to Supabase — dominant latency at scale, not queries.
9. [LOW] Index coverage thin: only `Message.conversation_key` indexed (`core/models.py:137`, mig `0005`). Hot filters unindexed: `Attendance.clock_out` (open-scan `:75`), `LeaveRequest.status` (`iexact` `:69-74`), `Employee.is_active` (`:68`), `ExpenseClaim.status`, `EmployeeAuditLog.timestamp` ordering (`core/views.py:358`). Add `db_index` on clock_out/status/is_active/timestamp before data grows; note `iexact` needs a functional/lower index to help on Postgres.
10. [MED] Static served by Django in ALL envs (`re_path static/… insecure=True` — `kumon_ems/urls.py:24`); `MEDIA` dev-only (`:27-28`, correct). No WhiteNoise/CDN, no `STORAGES` compression/hashing; `Message.attachment` FileFields (`core/models.py:140`) stream through Django. Fine locally, blocking + slow in prod.
11. [MED] Serving story ends at dev `runserver` (`README.md:75`, plain `get_wsgi_application()` — `kumon_ems/wsgi.py:15`): single-threaded, no gunicorn/uvicorn, no workers/timeouts/healthcheck. Any concurrent clock-in burst queues behind one thread regardless of DB.
12. [INFO] No caching layer: no `CACHES` in settings, summary uncached, JS uses `cache: no-store` (`static/js/dashboard.js:581,807`). Correct for mutable roster data; revisit only for (1).

## Verdict
No perf blocker at pilot scale: pages capped, queries are cheap counts/PK-ordered lists, throttles bound abuse. Prod-scaling order: WSGI server + static story (10, 11) → PG pooling (8) → throttle/bulk (5, 6) → indexes/cache (9, 1). Zero `select_related` is a code-review flag, not a runtime fault.
