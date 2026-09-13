# 03 — API Design & REST Consistency (round 3, cf89b71)

Scope: `api/urls.py` (24 paths), project/core redirects, `core/exception_handler.py:4-26`,
409 rule, pagination/ordering, messages/claim-statuses, ExpenseClaim gap. Round-2 settled items noted FIXED, not re-argued.

## Route table (verified 24 paths, `api/urls.py:30-111`)
- OK — 24 `path()` entries; trailing-slash consistent; creates→201, PATCH→200, clock-out→200 `{message}` (`core/views.py:272-275`), missing-open-row→404 (`:255-258`).
- FIXED since r2 — soft-delete now 200 with body (`core/views.py:191-199`); Department ordered (`:96`); 409 unified (see below); `EXCEPTION_HANDLER` wired (`kumon_ems/settings.py:192`).
- LOW — `attendance/clock-out/` (`api/urls.py:54-58`) still after `attendance/<uuid:pk>/` (`:49-53`); safe only via uuid converter. Reorder action first.
- LOW — naming: `leaves/`, `performance/` (`api/urls.py:59,91`) singular vs plural rest; `audit-logs/` (`:101`) read-only ListAPIView, fine but reads as collection.
- LOW — dup route names: `/signup/`, `/auth/` 302→`/login/` (`kumon_ems/urls.py:14-15`) vs same names 200 under `/core/` (`core/urls.py:8-9`). Keep one canonical set.

## Error envelope (`core/exception_handler.py:4-26`) — MED
- Handler normalizes raised `{detail}`→`{error: str}` (`:13-19`) and field-dicts→flattened `{error}` string (`:20-25`). Good.
- HOLE: hand-rolled `Response({"error": exc.detail})` (`core/views.py:121`) bypasses handler → `{error: {nested dict}}` vs handler's `{error: "flat string"}`. Route through `raise` or flatten at site.
- LOW: success shapes `{message}` (clock-out `:273`, session `:377,:385`) vs resource bodies elsewhere; acceptable for actions, document it.

## 409 rule — COHERENT (verify, was HIGH in r2)
- Email dup 409 both paths (`core/views.py:122-126,145-150`); attendance fast-path now `Conflict409` (`core/serializers.py:56`) + race 409 (`core/views.py:211`); shift overlap 409 (`core/serializers.py:103`); payroll-line dup 409 (`core/views.py:336`); multi-open clock-out 409 (`core/views.py:259-263`). No 400/409 split remains.
- MED — `ClaimStatus` POST is upsert (`core/views.py:406-412`) returning 201 always; no 200-vs-201 distinction, no detail route. Use PUT on `claim_id` or document upsert+200.

## Pagination / ordering — LOW
- Global `PageNumberPagination` size 10 (`kumon_ems/settings.py:185-186`); all generic lists paginated; `Message` relies on model `Meta.ordering` (`core/models.py:146`), acceptable.
- Gap (unchanged): no `page_size` param, no filter/search/`OrderingFilter` on any list; `get_queryset` conversation filter (`core/views.py:391-393`) is the only query affordance.

## messages / claim-statuses contracts — MED
- `messages/` (`api/urls.py:105`): query default `conversation="sarah"` (`core/views.py:392`) matches create default (`:397`); sender default `Marcus Williams` (`:398`) is demo leakage — require auth user instead. `attachment` write-only + `attachment_url` absolute (`core/serializers.py:142-163`) OK; validate demands text-or-file (`:165-170`) OK.
- `claim-statuses/` (`api/urls.py:106-110`): `perform_create` ignores `validated_data`, uses raw `request.data` + sets `serializer.instance` without `save()` (`core/views.py:406-412`) → unvalidated `claim_id`/`status=None` can 500; response body may be stale. Validate + return 200 on update.

## ExpenseClaim gap — HIGH
- `ExpenseClaim` model+serializer+list/detail views exist (`core/models.py:116-125`, `core/serializers.py:129-132`, `core/views.py:415-422`) but ZERO routes in `api/urls.py` → dead API; frontend claims necessarily static. Wire `expense-claims/` + `/<uuid:pk>/` or delete the code.

## Versioning/docs — LOW
- No `/api/v1/` or DRF versioning; `auth-token/`+403-for-anon still undocumented in README workflows (r2 A10/A11 open).
