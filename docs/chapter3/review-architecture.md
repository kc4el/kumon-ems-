# Review A — Architecture & Data (SOP1–SOP5)

## 1. Layering: all logic in `core`, `api/` is a shim
- `api/views.py:1-3`, `api/models.py:1-3` are empty stubs; `api/urls.py:3` imports every view from `core.views`. No service/selectors layer: Supabase Auth create+rollback (`core/views.py:94-138`), clock-out lookup (`core/views.py:156-175`), dashboard aggregates (`core/views.py:46-76`) all live in views. `core/urls.py` serves only templates. Finding: works, but Chapter 3 cannot claim a decoupled API layer — recommend `core/` (domain) vs `api/` (transport) split or removing `api/`.
- DRF: global `PageNumberPagination` size 10 (`kumon_ems/settings.py:157-160`), but `DepartmentListCreateView` sets `pagination_class=None` (`core/views.py:82`) — inconsistent contract. No filter/search backends on any list view; no permission classes on any view (all endpoints unauthenticated — see SOP4).

## 2. Model design (`core/models.py`)
- UUID PKs everywhere (`models.py:7,25,41,52,63,74,81,90,98`): justified — `EmployeeListCreateView` forces `payload["id"] = auth_user.id` (`core/views.py:106-120`) so local PK == Supabase Auth id. Cost: `order_by("id")` (`core/views.py:91,189,199,209,219`) is random order; use `-created_at`/name.
- `Department.manager → Employee SET_NULL` (`models.py:10-16`) + `Employee.department SET_NULL` (`models.py:30-32`): circular, nullable both ways. Supports org chart; missing: no constraint manager ∈ department; deleting a manager silently orphanages leadership.
- `Attendance` unique (`employee`,`date`) (`models.py:47-48`) + serializer guard (`core/serializers.py:33-41`): SOP2 double-clock-in prevention. Gaps: app-level check only (no `IntegrityError` handling in `core/views.py:146-148`, race-prone); `.get(employee, clock_out=null)` (`core/views.py:162-164`) can raise `MultipleObjectsReturned`; no `clock_in ≤ clock_out` validation, no hours/overtime derivation.
- `PayrollRun`/`PayrollItem` split (`models.py:73-86`, CASCADE): correct batch header↔lines shape. Gaps: no `unique(payroll_run, employee)` → duplicate line items; `net_pay` client-writable, never computed (`base − deductions` unenforced); `is_processed` has no transition guard (plain CRUD `core/views.py:198-215`).
- `ShiftRoster` standalone (`models.py:62-70`): **no FK to Employee/Department, no date field** (times only). `signals.py:102-113` logs `instance.employee` via `hasattr` → always `None`. Conflict detection / assignment is schema-impossible (see SOP3).
- `EmployeeAuditLog.employee SET_NULL` (`models.py:97-101`): preserves rows on employee delete (good). Gaps: `action` free-text ≤255 chars, no actor FK/IP/object-id; signals log every save (`core/signals.py:46-151`) — noisy, PII-heavy, no purge.
- Serializers: `fields="__all__"` on all 8 (`core/serializers.py:16-77`) — `id`, `is_active`, `net_pay`, `status` client-settable; only Attendance validates.

## 3. Supabase vs SQLite split
- `DATABASES` is local SQLite (`kumon_ems/settings.py:91-96`); `supabase_client.py:1-16` is Auth-only (`auth.admin.create/delete_user`). No Supabase Postgres/RLS/realtime. Dual-write Auth→local DB with manual rollback (`core/views.py:128-135`), no `transaction.atomic`; import-time `ValueError` if `.env` missing (`supabase_client.py:13-14`) crashes whole app. Deleting an Employee never deletes the Auth user (orphaned login). Service-role key stays server-side (correct) but no rotation story.

## 4. SOP support vs missing
- **SOP1 centralized DB**: SUPPORTED — one DB, 8 models, `DashboardSummaryView` aggregates. MISSING: canonical store is a local SQLite file, not the claimed cloud DB; no cloud migration/sync story.
- **SOP2 verification/payroll**: SUPPORTED — unique attendance, clock-out endpoint, run/item split. MISSING: no hours/overtime math, no approval state machine (`status` free text, `LeaveRequest` `models.py:58`), no payroll computation/verification.
- **SOP3 shifts/notifications**: NOT SUPPORTED — unassignable roster, no overlap query, no notification model/channel. (Paper §1.5 scope lines 83-85 itself excludes automation — flag this tension in Ch.3.)
- **SOP4 security**: SUPPORTED — Auth-provisioned users, audit trail. MISSING: zero DRF auth/permission classes, no RLS/encryption-at-rest narrative, overexposed serializers.
- **SOP5 30-day deletion**: ENTIRELY MISSING — no resignation/offboard status, no `deleted_at`/retention timestamp, no purge job; worse, `CASCADE` on Employee hard-deletes attendance/payroll/leaves instantly, contradicting retention; only audit shells survive via SET NULL.
