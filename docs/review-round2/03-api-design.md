# Review 3 — API Design & REST Consistency (contract audit)

Branch chore/standard-format @ c8690ed. Scope: HTTP contract only.

## Status codes
- HIGH — Same condition, two codes: attendance double-clock-in fast path → 400 via
  serializer `ValidationError` (`core/serializers.py:48-50`, `api/tests.py:204`) but race
  path → 409 via `Conflict409` (`core/views.py:170`, `core/exceptions.py:4-7`). Pick one.
- HIGH — No 409 rule: email-dup → 409 (`core/views.py:114-118`), attendance-race → 409,
  but payroll-line dup → 400 (`core/views.py:282-284`, `api/tests.py:287`) and shift
  overlap → 400 (`core/serializers.py:96-99`, `api/tests.py:387`). Document or unify.
- MED — Soft-delete lies: `DELETE /api/employees/<uuid>/` deactivates yet returns 204
  empty (`core/views.py:155-158`, `api/tests.py:357`); resource still `GET`s 200. Return
  200 with representation or `Allow` note.
- OK — Creates → 201 (incl. custom employee `post`, `core/views.py:135`); PATCH → 200
  (`api/tests.py:346`); clock-out action → 200 `{message}` (`core/views.py:224-227`,
  correct, no resource created); missing-open-row → 404 (`core/views.py:207-210`).
- LOW — 502 only for Supabase-create failure (`core/views.py:147`); acceptable, no timeout split.

## Pagination / ordering
- FIXED (round-1 stale) — no `pagination_class=None` remains; all 9 lists return
  `{results: []}` (`api/tests.py:56-57`) via global `PageNumberPagination` size 10
  (`kumon_ems/settings.py:169-170`). Gap: no `page_size` param, no filter/search backends.
- MED — `DepartmentListCreateView` has no `order_by` (`core/views.py:87-89`); other 8 lists
  are ordered (`views.py:98,162,236,246,256,266,296,306`). Add `order_by("name")`.

## Error bodies
- HIGH — Three shapes: hand-rolled `{error}` (`core/views.py:82,106,116,146,183,191,208,213,219,230`),
  raised `Conflict409`/DRF → `{detail}` or field dicts (no `EXCEPTION_HANDLER` in settings),
  `obtain_auth_token` failure → `{non_field_errors}` (`api/urls.py:98`). Add exception handler
  normalizing to one envelope.

## Routes / redirects / misc
- LOW — Naming: `leaves/` vs singular `performance/` (expect `performance-reviews/`);
  `audit-logs/` is read-only `ListAPIView` (`core/views.py:305`) but reads as collection.
- LOW — `attendance/clock-out/` declared AFTER `attendance/<uuid:pk>/` (`api/urls.py:45-54`);
  safe only via uuid converter — reorder action first for robustness. All routes trailing-slash OK.
- LOW — `/signup/`, `/auth/` → 302 to `/login/` (`kumon_ems/urls.py:14-15`, `permanent=False`
  correct); confusing dup: `core/urls.py:8-9` serves same names with 200 under `/core/`.
- MED — `POST /api/auth-token/` exists+tested (`api/urls.py:98`, `api/tests.py:32-36`) but
  README workflows table (`README.md:7-14`) omits it, the `Token` scheme, and the 403-for-anon
  rule (`api/tests.py:28-31`).
- INFO — OPTIONS/HEAD default DRF metadata only; anon OPTIONS on guarded routes → 403.
  No versioning: no `/api/v1/` or DRF versioning class — flag before any breaking change.
