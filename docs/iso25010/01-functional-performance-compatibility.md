# ISO/IEC 25010 — 01 Functional Suitability, Performance Efficiency, Compatibility

Scope: PR branch `chore/standard-format` (Django 6.1 + DRF). No code changes.

## 1. Functional Suitability

| Sub-characteristic | Verdict | Evidence |
|---|---|---|
| Completeness | PARTIAL | SOP1/2 present (`core/views.py:59-92,202-280,313-344`; `api/urls.py:32,44-90`). SOP3 shifts yes, notifications gap — only `Message` model (`core/models.py:135`) + `messages/` (`api/urls.py:105`), no push/scheduling. SOP5 purge manual-only (`purge_resigned.py:13-46`). |
| Correctness | PARTIAL | 47 tests green incl. 409/400 paths (`api/tests.py:192-223,312-346,452-532`). Guards: unique_together (`core/models.py:52-58`), overlap check (`core/serializers.py:81-104`), net_pay server-computed (`core/views.py:323-336`). Races remain: overlap check-then-insert, clock-out count/first re-query (`core/views.py:248-264`). |
| Appropriateness | PARTIAL | Dashboard/employees/leaves live via REST; payroll manual-post (never derived from attendance); leave↔roster unlinked; demo-fallback/toast-only views confuse task fit (`COMPILED.md` F1/F2/F11). |

## 2. Performance Efficiency

| Sub-characteristic | Verdict | Evidence |
|---|---|---|
| Time behaviour | PARTIAL | Pagination `PAGE_SIZE 10` (`kumon_ems/settings.py:185-186`) + ordered querysets bound list cost; but `DashboardSummaryView` fires 5× `count()` per GET (`core/views.py:67-75`); no `select_related/prefetch_related` anywhere; `select_for_update` no-op on SQLite (`core/views.py:249`). |
| Resource utilisation | PARTIAL | SQLite default, Postgres when `DB_HOST` set (`kumon_ems/settings.py:95-114`) — no pooling/cache config; throttles `anon 100/day, user 1000/day` (`settings.py:187-191`, test `api/tests.py:571`); zero server caching (only `cache: no-store` in JS). SQLite serialises writes; fine for pilot, not roster peak. |
| Capacity | PARTIAL | 10/page caps payload; throttle caps abuse but also batch imports (~1000 writes/day/user); no bulk endpoints, no async/scheduler (purge manual); CASCADE on employee delete risks large fan-out (`core/models.py:45,64,99`). |

## 3. Compatibility

| Sub-characteristic | Verdict | Evidence |
|---|---|---|
| Co-existence | PASS | Same-origin vanilla JS + DRF JSON; no WS/polling contention; CORS localhost-only + credentials (`kumon_ems/settings.py:167-174`); Supabase confined server-side (`core/supabase_client.py:11-16`), no JS key leak (0 `supabase` hits in `static/`). |
| Interoperability | PARTIAL | Contract: REST/JSON, UUID PKs, ISO-8601 validated (`core/views.py:234-243`); dual auth session+token (`settings.py:178-184`, `api/urls.py:102-104`) but JS sends zero `Authorization` headers (static search 0 hits) so writes 403; error envelope unified to `{error}` (`core/exception_handler.py:4-26`); hard Supabase coupling on employee create → 502 without it (`core/views.py:131-163`). Browser: plain `fetch`, no polyfill/browserlist — modern evergreen only. |
