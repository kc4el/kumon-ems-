# Kumon EMS — 50 open issues (7-agent sweep, 2026-09-13)

Branch: `chore/standard-format`. Prior plan T1–T8 verified landed (8/8 commits, 133 tests OK).
This is a candidate list from read-only review — spot-check file:line before implementing.
Severity: CRITICAL = data loss / auth bypass / migrate abort. HIGH = wrong money/time/access. MEDIUM = 500s, noise, UX lies. LOW = hygiene.

## Counts
- CRITICAL: 3 | HIGH: 27 | MEDIUM: 17 | LOW: 3 (total 50)
- By area: Auth 8, Leave/Attend/OT/Swap 7, Payroll/Purge/Resign 7, API validation 7, Frontend 7, Models/Migrations 8, Security/Config 6

---

## 1. Auth, sessions, owner-scoping (8)

| # | Sev | Issue | File:line | Detail / repro |
|---|-----|-------|-----------|----------------|
| A1 | CRITICAL | Resign fail-open leaves creds valid | core/views.py ~264-315 | destroy() catches Supabase + local-kill errors, still 200. Old token/session keeps working. Repro: resign with Supabase down → reuse old token → still 200. Fix: block resigned users at auth/permission layer + retry queue. |
| A2 | HIGH | Resign kill looks up users by email, not FK | core/views.py ~285-291 | `filter(email__iexact=instance.email)` misses renamed users, can hit wrong row. Fix: kill `instance.user` + tokens/sessions by id. |
| A3 | HIGH | Inactive/resigned never blocked at login | core/views.py ~795-807 | SessionLogin + token obtain never check `employee.is_active`. Fix: auth gate on is_active/resigned_at. |
| A4 | HIGH | Tokens never expire; logout kills one cred only | core/views.py ~810-815, api/urls.py ~161 | Permanent token, session-logout leaves tokens alive and vice versa. Fix: expiry/rotation + kill-all on logout/resign. |
| A5 | HIGH | Create endpoints accept arbitrary employee FK | core/views.py ~322,464,548,613,737,772,855 | perform_create saves client-supplied employee id. Any user can file leave/attendance/expense for anyone. Fix: force `request.user.employee_profile` for non-staff. |
| A6 | HIGH | Unscoped reads/mutations (IDOR remnants) | core/views.py ~407,518,585,818 + Dept/PayrollRun/AuditLog | LeaveBalance, ShiftConflict, clock-out take arbitrary employee id; Message filters only by conversation_key; Dept/Payroll/Audit have no scoping. Fix: ownership check on each. |
| A7 | HIGH | Owners PATCH privileged fields on self | core/views.py ~254-257, serializers ~32-45 | role/is_active/department/email mutable by owner → self-promote, reactivate after resign. Fix: staff-only serializer/whitelist. |
| A8 | MEDIUM | Signup strip is anon-only; anon no-password orphans | core/views.py ~148-168 | Authed non-staff can set role/is_active at create; anon without password makes user=NULL orphan. Fix: strip for all non-staff; require password or link flow. |

## 2. Leave / attendance / OT / swap (7)

| # | Sev | Issue | File:line | Detail |
|---|-----|-------|-----------|--------|
| LA-01 | HIGH | Leave status free text, case-sensitive downstream | serializers.py ~108, views.py ~508,599 vs 89-94 | `approved` persists but balance/conflict filters use `Approved`; dashboard uses iexact → counts disagree. Fix: ChoiceField Pending/Approved/Rejected. |
| LA-02 | HIGH | Attendance clock_out before clock_in via direct write | serializers.py ~48 | Only correction serializer + clock-out view check ordering. Direct POST/PATCH saves negative durations → corrupts OT math. Fix: validate in AttendanceSerializer. |
| LA-04 | HIGH | OT slip update drops fields, any status | core/views.py ~574-582, serializers ~147 | perform_update saves status only, silently ignores rest; no status choices. Fix: 400 on employee/attendance change + ChoiceField + date check. |
| LA-05 | MEDIUM | OT hours stale after correction; multiplier unbounded | views.py ~552-571, models ~78-80 | Hours computed once; correction-approval never recomputes; multiplier accepts 0/negative/99. Fix: recompute on approval + Min/Max validator. |
| LA-06 | MEDIUM | Allocation update 500 on collision; zero-day rows | views.py ~489-492, models ~139 | Create maps IntegrityError→409, update has no guard → 500; days_total allows 0. Fix: update guard + require >0. |
| LA-07 | HIGH | Swap guard bypass + races | views.py ~652-686, serializers ~194 | Any status string persists incl. on decided swaps; approve skips same-date/conflict re-checks, locks rosters not swap row → double-book race. Fix: whitelist statuses, freeze decided, re-validate under locked swap. |
| LA-08 | MEDIUM | Swap/leave notifications incomplete, stale audit | views.py ~664-724, signals.py ~169-176,251 | Reject notifies requester only; create sends none; audit reads unlocked relations; over-balance warning inherits LA-01 miss. Fix: notify both parties, refresh_from_db. |

## 3. Payroll / purge / resign / audit (7)

| # | Sev | Issue | File:line | Detail |
|---|-----|-------|-----------|--------|
| P1 | HIGH | Purge negative days → 500 | views.py ~885-913, purge_resigned.py ~25-27 | `int()` unguarded, call_command CommandError unhandled. Fix: reject <0 with 400. |
| P2 | HIGH | dry_run 'false' still dry (verified) | views.py ~897-909 | Only `0/no/off` mean real; `'false'/'False'/'f'` stay dry → client asking real purge gets dry run. Fix: explicit true/false sets. |
| P3 | HIGH | Negative payroll net accepted | views.py ~746-760, models ~191-200 | No validators on base/deductions; deductions>base → negative net persisted. Fix: MinValueValidator + net>=0. |
| P4 | HIGH | Processed run not locked | views.py ~727-769, models ~184-188 | Lines addable/editable on closed run; no start<=end check; PATCH can move line across runs. Fix: guard is_processed + period validation. |
| P6 | HIGH | Purge audit loses attribution; audit log unscoped | purge_resigned.py ~37-41, models ~233-237, views ~783-785 | Audit employee=None then row deleted; FK SET_NULL wipes history; list view has no scoping. Fix: snapshot id/email in text + scope view. |
| P7 | MEDIUM | Missing + noisy notifications | views.py ~866-879, signals.py ~164-181 | None for payroll/resign/purge/claims; Pending submit fires noise; mark-read 404s for user-less owners. Fix: event matrix + owner-or-staff check. |
| P8 | HIGH | Uploads unlimited; no exit-doc path | serializers ~283-318, models ~240-248 | `FILES` direct index → KeyError risk; no type/size caps; resign takes no clearance docs. Fix: get() + validators + exit-doc field. |

## 4. API validation edge cases (7)

| # | Sev | Issue | File:line | Detail |
|---|-----|-------|-----------|--------|
| V2 | HIGH | No status state machine | views.py swap ~657 vs leave/expense/OT | Approved↔Rejected↔Pending flips with no 409/audit. Fix: allow-list transitions. |
| V3 | MEDIUM | Role free text, spoofable | models.py ~34, views.py ~167 | `Admin`, blank, 200-char junk persist; anon strip is exact-key only. Fix: choices + trim. |
| V4 | HIGH | Attendance update skips dup guard | serializers.py ~57-63 | `if not self.instance` → PATCH onto existing pair bypasses 409 fast path. Fix: check on update excluding self. |
| V5 | HIGH | Message validate crashes w/o context | serializers.py ~313-318 | `context['request']` KeyError; `"   "` passes; no size/type cap. Fix: .get + strip + caps. |
| V6 | HIGH | OT multiplier + date (dup of LA-05, serializer side) | models.py slip, serializers ~160 | Negative/zero multiplier; slip date vs attendance.date unchecked. Fix: validators. |
| V7 | MEDIUM | leave_type case fragments balances | models.py alloc, views.py balance | `vacation` vs `Vacation` splits keys, bypasses dup guard, 0-default. Fix: normalize/choices. |
| V8 | MEDIUM | Score/overnight/form gaps | models.py review, serializers roster | Absurd scores, no overnight shifts, negative break_mins, whitespace UUIDs form-vs-JSON differ. Fix: ranges + overnight policy + trim. |

## 5. Frontend honesty / dead controls (7)

| # | Sev | Issue | File:line | Detail |
|---|-----|-------|-----------|--------|
| F1 | MEDIUM | View Full Profile dead | index.html roster cards, dashboard.js loadEmployeeDirectory | No handler (static) or re-opens list (live). Fix: wire modal or remove. |
| F2 | MEDIUM | Promote/Transfer permanently disabled | index.html #promoteFormContainer/#transferFormContainer | Hardcoded disabled, forms unsubmittable. Fix: connect or hide. |
| F3 | MEDIUM | Offboarding uploads disabled, finalize still claims clearance | index.html #removeFormContainer | 4 upload buttons disabled; text admits placeholders. Fix: disable finalize or implement. |
| F4 | HIGH | Onboarding uploads fake success | index.html #onboardingModal | Buttons only toast; handleOnboarding drops assets/docs yet toasts 'credentials issued'. Fix: real POST or remove. |
| F5 | MEDIUM | Pagination/calendar/week-nav dead | index.html claims/history/audit/daily/shift | Buttons toast or nothing. Fix: real paging or remove. |
| F6 | MEDIUM | Exports/receipts pretend | index.html Export Register, receipt links | Toast-only, no file (unlike exportAuditLogs CSV). Fix: generate or label demo. |
| F7 | HIGH | Grievance/advance/roster/claim actions toast-only | dashboard.js handleGrievanceSubmit, handleRequestAdvance, shift assign/remove, claim actions | No POST; DOM-only edits; Batch Approve '(0)' hardcoded. Fix: persist or mark demo. |

## 6. Models / migrations / integrity (8)

| # | Sev | Issue | File:line | Detail |
|---|-----|-------|-----------|--------|
| M1 | HIGH | Backfill imports live models | 0019_backfill_employee_user.py ~4-17 | Bypasses historical registry → replay drift. Fix: apps.get_model. |
| M2 | HIGH | Backfill orphans + nondeterministic match | migrations_compat.py ~24-38 | NULL forever, no follow-up; `.first()` unordered; reverse noop. Fix: ordered match + report + noop-safe. |
| M3 | MEDIUM | Employee.user SET_NULL orphans staff | models.py ~41-47 | Deleting User leaves active employee login-less silently. Fix: PROTECT/deactivate. |
| M4 | CRITICAL | FK→OneToOne with no dedupe | 0021_alter_overtimeslip_attendance.py ~13-20 | Pre-existing dup slips abort 0021 on Postgres. Fix: dedupe RunPython before AlterField. |
| M5 | HIGH | Slip.employee vs attendance.employee unchecked | models.py ~72-77 | Alice slip on Bob attendance corrupts payroll. Fix: CheckConstraint/clean. |
| M6 | HIGH | Partial unique drifts SQLite↔Postgres | models.py ~60-69 | Partial clock_out-NULL index + legacy unique_together overlap; one-open-ever blocks new-day clock-in. Fix: per-day open constraint, test both DBs. |
| M7 | MEDIUM | Python-only validators, legacy unique_together | models.py ~133-144 | days_total/amount bypassable via SQL; Allocation/PayrollItem legacy tuples. Fix: CheckConstraints + named UniqueConstraints. |
| M8 | MEDIUM | Rosters double-bookable + ghost + self-swap | models.py ~147-181 | Nullable employee/date, no (employee,date,start) unique; no end>start/break>=0; self-swap allowed. Fix: constraints. |

## 7. Security / config / hygiene (6)

| # | Sev | Issue | File:line | Detail |
|---|-----|-------|-----------|--------|
| S1 | CRITICAL | SECRET_KEY fallback weakens fail-fast (verified) | kumon_ems/settings.py ~29-32 | Dev fallback key present; ensure prod env always sets real key. Never rotate here — owner job. |
| S2 | MEDIUM | Static served insecure unconditionally | settings.py ~35, urls.py ~24 | `serve(insecure=True)` bypasses DEBUG gate; MEDIA 404 in prod while uploads write disk. Fix: gate static, serve/store media consistently. |
| S3 | MEDIUM | CORS hardcoded localhost + credentials | settings.py ~36-42,167-174 | No env override → prod breaks or tempts ALLOW_ALL. Fix: env-driven origins. |
| S4 | HIGH | Zero SESSION/CSRF/SECURE hardening | settings.py missing | No HSTS/SSL-redirect/secure cookies. Fix: set for prod (office machine + future mobile API). |
| S5 | MEDIUM | Dashboard AllowAny + unthrottled token endpoint | settings.py ~177-193, views ~79-83 | Public aggregates aid enumeration; anon 100/day shared. Fix: scope/throttle. |
| S7 | HIGH | Chat uploads unrestricted, guessable paths | models.py ~245-246, serializers ~284-320 | Any type/size under MEDIA_ROOT date path. Fix: allowlist + size cap + random names. |

Dropped to reach 50 (lowest value / overlap): LA-03 date-vs-datetime, P5 dead perform_destroy, V1 case-normalization wording, F8 hardcoded greeting/KPI, S6 pagination dup, S8 TZ/format hygiene.

## Suggested next step (policy Q before plan execution)
Confirm: (1) mobile = untrusted client — enforce server-side ownership everywhere (A5/A6 first)? (2) Token expiry window acceptable? (3) Purge dry_run canonical values? Then one revertable commit per fix, TDD, no push until told.
