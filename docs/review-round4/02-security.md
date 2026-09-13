# 02 Security — Round 4 (NEW since round-3 cf89b71; HEAD 4c6864c)

Scope: 8 new endpoints (attendance-corrections, leave-allocations, leave-balances,
overtime, shift-swaps, shift-conflicts, expense-claims, notifications, purge-run).
Round-3 items (history secrets, token expiry, coarse throttles) unchanged — not repeated.
Fixed since round 3: message sender now bound to request.user; ClaimStatus uses
validated_data + atomic + ChoiceField; expense-claim routes wired with amount/status guards.

## Findings (new)

1. [HIGH] Unscoped querysets on all new CRUD views — any authed user (incl.
   self-signed-up) can list/get/patch/delete ANY employee's rows. No get_queryset
   scoping or ownership check anywhere.
   - core/views.py:265,270 (AttendanceCorrection list/detail)
   - core/views.py:392,406 (LeaveAllocation list/detail)
   - core/views.py:464,486 (OvertimeSlip list/detail)
   - core/views.py:534,539 (ShiftSwap list/detail)
   - core/views.py:750,755 (ExpenseClaim list/detail)
2. [HIGH] Notification visibility leak + IDOR write. List returns EVERY employee's
   notifications; mark-read fetches by pk with no ownership check, then echoes the
   row (read + tamper anyone's inbox). — core/views.py:759-770
3. [HIGH] Arbitrary-employee read via query params, no ownership check. Any authed
   user passes any `?employee=<uuid>` and reads balances/conflicts.
   - core/views.py:433 (LeaveBalanceView) · core/views.py:495 (ShiftConflictView)
4. [HIGH] Self-approval / missing role gate on new approval paths. Any user can
   approve anyone's (incl. own) overtime, correction, swap, claim; anyone can mint
   any employee's leave allocation. No staff/manager check (purge-run excepted).
   - core/views.py:273 (correction patch) · core/views.py:489 (overtime
     perform_update) · core/views.py:552 (swap patch) · core/views.py:391
     (allocation create) · core/serializers.py:242 (claim status writable)
5. [MED] Mass-assignment leftovers. ExpenseClaim `employee`+`status` writable →
   reassign claim to another employee / self-approve (core/serializers.py:242-255).
   AttendanceCorrection `status` writable via PUT (patch guard covers PATCH only)
   + `attendance` FK reassignable (core/serializers.py:66; core/views.py:269).
   ShiftSwap rosters rewritable (core/serializers.py:181).
6. [MED] Overtime attribution spoof. `employee` is client-supplied; the only check
   is attendance.employee == supplied employee, so attacker files a slip NAMING
   any victim whose attendance id they guess/list. — core/views.py:463-483
7. [MED] Anon signup spam amplified. POST employees/ stays AllowAny and now also
   mints a valid Django login when `password` supplied — unauthenticated mass
   creation of Employee rows + usable accounts; no captcha, anon throttle still
   global 100/day. — core/views.py:119-178; kumon_ems/settings.py:191

## Verified clean (no new issue)

- XSS: all new renderers (activity feed, roster, payroll, audit) escapeHtml;
  breadcrumb innerHTML uses static map only. — static/js/dashboard.js:332,1547,1580,1645,1695
- CSRF: apiFetch now sends X-CSRFToken incl. FormData + 401→login.
  — static/js/dashboard.js:27-40
- PurgeRunView correctly IsAdminUser-only. — core/views.py:772
- CORS allowlist localhost-only; no password/token/secret in logs (email only).
