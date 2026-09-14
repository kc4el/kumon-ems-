# SOP vs Accomplished — alignment check (2026-09-13)

Branch: `chore/standard-format`. Wave 1: 211 tests OK. Source: 3-agent docs sweep.

## SOP inventory (from docs/chapter3/CHAPTER3.md + _coordination.md)
- SOP 1: Centralized data (attendance, salary, performance, leaves) — O1 single store + dashboard aggregates
- SOP 2: Attendance tracking + payroll calc — O2 duplicate-proof attendance + server-computed net pay
- SOP 3: Shift coordination — O3 rosters + overlap guard + leave co-visible (notifs still missing per Ch.3)
- SOP 4: Data safety + privacy — O4 Supabase server-side auth + audit trail
- SOP 5: Resignation + 30-day purge — O5 soft-deactivate then purge_resigned erasure (unscheduled)
- Prior grades: S1 COVERED, S2 COVERED (manual payroll), S3 PARTIAL, S4 PARTIAL, S5 PARTIAL
- Scope note: no standalone Ch.1 Objectives section in docs/ — objectives above are SOP-derived (§3.4 contracts). Standing scope: desktop ADMIN-ONLY.

## Backend — partially-aligned
Aligned (10): T1 inactive gate (staff bypass) in permissions.py; T2 FK resign kill in views.py; decided-409 leave/OT/swap; OT serializer hardening; leave title-case; OT clean() + per-day constraint + mig 0022-0023; onboarding docs endpoint; pagination default; claim/advance/grievance wiring; allocation PATCH 409.
Gaps (8): A3 no login-time is_active check; A7 owner PATCH privileged fields; A5 arbitrary employee FK on create; P1/P2 purge negative-days + dry_run 'false'; P3/P4 payroll negatives + unlocked processed runs; LA-02 clock_out ordering on direct write; A4 tokens never expire; M4 mig 0021 no-dedupe (PG abort risk).

## Frontend — mostly-aligned
Aligned (8): onboarding upload wired (10MB + PDF/JPG/PNG); live ?page=N pagers (claims/advances/audit) with demo fallback + toasts; claim decision endpoint + live batch count; advances POST + register; grievance POST (key=grievance); roster POST + conflict flags; dead nodes fixed; design tokens kept + LIVE/DEMO badge.
Gaps (7): grievance case buttons toast-only; bell '3 priority' hardcoded; attendance/settlement exports toast-only; chat file picker no guards; tour copy stale ('coming soon' for wired features); audit rows lose category/actor; wizard class drift.

## Bottom line
SOP 1-2 COVERED, SOP 3-5 PARTIAL — Wave 1 closed honesty + validation gaps but not: login gate, write-ownership forcing, purge/payroll guards, token lifecycle, notif matrix, purge scheduler/UI. Those are the queued 39 remainder.
