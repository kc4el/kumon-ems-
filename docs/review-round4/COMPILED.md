# Review Round 4 — Compiled (NEW only vs round 3)

Date: 2026-09-12 · Branch: chore/standard-format · HEAD: 4c6864c
Scope: synthesis of round-4 reviews only — no new auditing, no code changes, no test runs.
Sources: 01-backend-bugs.md (01) · 02-security.md (02) · 03-frontend-bugs.md (03) · 04-data-integrity.md (04) · 05-auth-sessions.md (05)

## Operating assumption (2026-09-12, owner-directed — re-grades everything below)

The desktop web app is ADMIN-ONLY on an office machine; employees use a
MOBILE app (to be built) against the same API. Consequences applied in this
revision: (a) every IDOR/unscoped-read finding is now MOBILE-BLOCKING —
untrusted clients will call these endpoints; (b) token lifecycle (expiry,
revocation, logout) moves from P1 to P0 — the mobile app cannot use session
cookies; (c) self-approval findings resolve into a two-sided flow (employee
requests on mobile, admin approves on desktop) instead of a role system on
web; (d) desktop-only UX findings (tour, widgets, badges) drop in priority
but stay valid; (e) three NEW mobile-readiness items added as findings
16–18. Severities below marked [↑] were raised by this revision.

## Top-15 deduped findings (severity-ranked, one line each)

[CRITICAL] [↑] Unscoped querysets on all new CRUD views let any authed user list/get/patch/delete anyone's rows — MOBILE-BLOCKING: untrusted mobile clients call these directly (core/views.py:265,270,392,406,464,486,534,539,750,755) (02)
[HIGH] Role gate reframed by two-sided flow: approvals move to admin desktop, requests come from mobile — enforce at the view layer (approve endpoints staff-only, request endpoints owner-scoped), not a web role system. Until then, any user self-approves; PUT bypasses PATCH guards (core/views.py:273,489,552,391; core/serializers.py:66,181,242) (01,02)
[HIGH] ShiftSwap double-approve race (check outside tx, swap row never re-locked) + app-only pending `.exists()` guard allows duplicate pendings under concurrency (core/views.py:552-563,586-615; core/serializers.py:209-216) (01,04)
[HIGH] Purge/offboard deletes Supabase user + Employee but orphans Django User + DRF token (forever-valid); re-onboard then bricks on duplicate username IntegrityError (core/management/commands/purge_resigned.py:33-45; core/views.py:175-181,213-237) (05)
[CRITICAL] [↑] Arbitrary-employee read via `?employee=<uuid>` on balances/conflicts with no ownership check — MOBILE-BLOCKING: becomes my-leaves/my-roster scoping (core/views.py:433,495) (02)
[CRITICAL] [↑] Notification leak + IDOR: list returns everyone's rows, mark-read has no ownership check — MOBILE-BLOCKING: inbox is per-employee data (core/views.py:759-770) (02,05)
[HIGH] OvertimeSlip has no DB uniqueness (double POST = 2 slips) and `employee` is client-supplied so slips can be filed against any guessable attendance id (core/models.py:64-83; core/views.py:463-483) (02,04)
[HIGH] Stored-XSS via unvalidated `attachment_url` assigned to `link.href`, accepting `javascript:` payloads (static/js/dashboard.js:1131-1136) (03)
[HIGH] ShiftRoster overlap guard is app-only `.exists()` with no DB exclusion constraint; concurrent overlapping inserts both succeed (core/serializers.py:168-177) (04)
[MED] OvertimeSlip PUT/PATCH silently drops all fields but `status`; status can regress Approved→Pending with no guard (core/views.py:489-492) (01)
[MED] Correction approve ignores resigned/deleted employee (no is_active guard, unguarded Attendance.get → 500) and unlimited Pending rows per attendance allow spam/double-approve (core/views.py:290-321; core/models.py:85-100) (01,04)
[MED] Leave/allocation validation gaps: no end<start, free-text status/leave_type (self-approve by POST), unbounded year/days_total/multiplier/score, case-sensitive "Approved" mismatch, detail PUT/PATCH lacks IntegrityError→409 (core/serializers.py:108-147,220-239; core/models.py:120,125; core/views.py:405-407,418,423,504-510) (01,04)
[MED] N+1 on all bare list querysets (FK-heavy serializers, zero select/prefetch) + per-type loop queries in LeaveBalanceView (core/views.py:241,265,382,392,464,534,539,638,433-460) (01)
[MED] Unhandled-500 + noise cluster: unbounded LeaveBalance year, purge `bool("false")` dry_run + negative days, swap-reject null-employee notification, Attendance/OvertimeSlip date cross-checks missing, roster/correction double-fire signals + CASCADE audit loss on roster/attendance/employee delete (core/views.py:442-448,787,781-789,569,341,467-482; core/signals.py:84-123,164-181,250-261; core/models.py:67,87,147-152) (01,04)
[MED] Frontend + session hardening cluster: escapeHtml TypeError crash, tour double-start/Esc conflicts, badge race, widget-prefs crash, feed shape bug, `?next=` open redirect, logout leaves DRF token alive, AllowAny signup spam (global 100/day only), no SESSION_* hardening (static/js/dashboard.js:209,231-253,324,331,357-360,573-577,741-744,932-958,1190-1192,1256-1257,1432-1686; core/views.py:119-178,704-709; kumon_ems/settings.py:191) (02,03,05)
[CRITICAL] [NEW] No token lifecycle for mobile clients: DRF tokens never expire and session logout does not revoke them — mobile cannot use cookie sessions, so every install holds a forever-credential (api/urls.py:102; core/views.py:704-709) (assumption)
[HIGH] [NEW] No employee-scoped API surface: mobile needs my-leaves / my-shifts / my-payslips / my-notifications bound to the caller; current lists are admin-wide reads with no owner filter (core/views.py) (assumption)
[MED] [NEW] Push channel missing: notifications are inbox-poll only; mobile needs FCM/APNs delivery or a documented polling contract with badge counts (core/models.py:167-176) (assumption)

## Recommended fix order (mobile-first revision)

1. Owner-scoping + token lifecycle (new 16, 17; findings 1, 5, 6): Django User ↔ Employee link, owner-filtered querysets, expiring/refreshable tokens with logout revocation — nothing mobile ships before this.
2. Two-sided approvals (finding 2): approve endpoints staff-only, request endpoints owner-scoped; no web role system.
3. Credential lifecycle (finding 4): delete User + token atomically on purge/offboard; gate is_staff so purge is reachable.
4. DB integrity + races (findings 3, 7, 9, 12): unique OT per attendance, pending-swap/correction guards, exclusion constraint, allocation 409 on update.
5. 500s + N+1 + push contract (findings 13, 14, new 18): validate inputs, prefetch, document polling/badge counts for mobile.
6. Desktop sweep last (findings 8, 15): XSS href guard, escapeHtml coercion, tour/badge/widget fixes — admin console polish, not blocking.
