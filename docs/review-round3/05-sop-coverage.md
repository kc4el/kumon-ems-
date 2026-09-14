# SOP coverage re-grade (round 3, code @ cf89b71) + Chapter 3 diff (§§3.1–3.4)

Ch.1 numbering: S1 dashboard, S2 attendance+payroll, S3 shifts+notifications, S4 safety+UX, S5 resignation+30d delete.

## Verdict table (re-verified against code)

| SOP | Verdict | Evidence |
|---|---|---|
| S1 centralized dashboard | COVERED | `DashboardSummaryView` (`core/views.py:59-92`, route `api/urls.py:32`); six regions live in `static/js/dashboard.js`: summary `:1123`, directory `:1157`, onboard POST `:292`, leave POST `:676`, inbox `:806,871`, claim-status `:581,592`; LIVE/DEMO badge `:20,38-40` |
| S2 attendance + payroll | COVERED | `unique_together` + `one_open_attendance_per_employee` (`models.py:51-59`); 409 fast-path (`serializers.py:46-56`), atomic create/update (`views.py:206-223`); clock-out 404/409/400 ordering (`views.py:226-280`); `net_pay` server-computed, PATCH 400 not KeyError (`views.py:319-344`). Residual: payroll manually posted, never derived from attendance |
| S3 shifts + notifications | PARTIAL | Scheduling covered: `employee` FK + `work_date` (`models.py:76-79`), overlap + start<end guard (`serializers.py:81-104`). Notifications = inbox `Message` only (`models.py:135-146`, `api/urls.py:105`, JS `:806,871`); no shift/leave→notification link |
| S4 safety + UX | PARTIAL | Safety covered: validate-first + `delete_user` rollback (`views.py:117-163`); Session+Token, `IsAuthenticated` default (`settings.py:177-184`), public summary (`views.py:63`); session login/logout, CSRF + `?next=` bounce (`dashboard.js:18-32`); audit signals + read-only `audit-logs/`. UX partial: attendance/shifts/payroll/audit static (audit = DOM filter only, `:1023-1040`, no fetch) |
| S5 resignation + 30d delete | PARTIAL | `destroy` → 200 + `purge_on`, idempotent re-DELETE, resigned audit (`views.py:170-199`); purge fail-closed, `--days>=0`, per-employee txn + audit (`purge_resigned.py:23-45`); tests `core/tests.py:114-193`. Still no scheduler/UI trigger; CASCADE still wipes attendance/payroll/leaves on hard purge |

## Chapter-3 corrections (`docs/chapter3/CHAPTER3.md`)

- §3.4.4 flowchart (ll.114-118) STALE: shows "create Auth user → serializer valid? → rollback" (old inverted order). Code validates locally first (`views.py:117-126`), then creates Auth user (`:128-144`). Fix order; same for §3.4.4 text l.110 ("creates the Auth user before the local row").
- Fig.8 caption (l.13) + `figure7/figure8.html` ("47 tests") FALSE: `core/tests.py` is the only test file with 13 `def test` methods. Fix to 13.
- VERIFIED TRUE, no change: six live regions (§3.4.1 l.71 ✓ per JS lines above); Figs 7–8 refs (all 8 html files exist); DB-switch row (§3.2 l.19 + Table 2 l.50 ✓ `settings.py:95-114`); UNDER DEVELOPMENT rule (§3.2 l.23 ✓ `ExpenseClaim` views `views.py:415-422` with no route in `api/urls.py`, tag `figure2-erd.html:189-199`); 422→409 fixed (§3.4.2 flowchart ✓); §3.4.3 manual-link + no-notifications honesty (l.93 ✓); §3.4.5 soft-delete + unscheduled-policy honesty (l.127 ✓); "plain table, not tamper-proof" (l.123 ✓); token auth in §3.2 (l.19 ✓).
- Round-2 settled items closed by Ch.3 edits — not repeated except the two live errors above.
