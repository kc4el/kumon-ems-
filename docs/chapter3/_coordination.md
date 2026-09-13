# Ch3 Coordination (chore/standard-format)
## Sources
- Repo: Django 6.1+DRF, SQLite db.sqlite3, logic in core/views.py, api/views.py empty, 9 tables core/models.py.
- SOPs (IM G3): S1 dashboard; S2 verification+payroll; S3 shifts/conflicts/notifs; S4 safety/privacy; S5 resignation+30d delete.
- Shape (DSA Ch3): 3.1 Design; 3.2 Arch+Figure; 3.3 HW/SW tables; 3.4 per-SOP+flowcharts. Figs: Temp/kumon-arch.html, kumon-erd.html. Method: waterfall modified, sprint division.
## Split — trace ONLY assigned SOP, no overlap
- review-architecture.md — S1 ONLY (layering, ERD, DashboardSummaryView, arch fig). NOT payroll math, auth, shift UX.
- review-correctness-security.md — S2+S4+S5 ONLY (guards, payroll compute, auth/perms, serializers, CASCADE vs retention). NOT arch redesign/UX.
- review-ux-completeness.md — S3 ONLY + §1.5 scope tension (roster, conflicts, notifs, dashboard UX). NOT models/auth logic.
- CHAPTER3.md (author ONLY): sole 3.1–3.4 prose + tables + figures. ch3-aide-notes.md (aide ONLY): captions, table drafts, flowchart lists. No prose.
## Contracts
- Reviews: `## Finding` + file:line + SOPn tag + severity (Blocker/Major/Minor). Max 30 lines.
- Author: cites finding IDs; every SOP claim needs code/diagram evidence. Aide: bullets only.
## Top 10 (deduped A+B+C, severity-ranked)
1. [Critical/S4] Secrets in git history (.env+SECRET_KEY+creds in 597d245, untracked only at c5bd55f; fallback settings.py:28-31) — ROTATE keys, purge history (B3).
2. [Critical/S4] Zero authN/Z: no permission_classes (views.py:46-231), no DEFAULT_AUTH/PERMISSION (settings.py:157-160); 17 routes anonymous (B1).
3. [Critical/S4] Service-role key god-mode server-side (supabase_client.py:11); scope down / edge fn (B2).
4. [Blocker/S5] No 30d purge; CASCADE hard-deletes attendance/payroll/leaves (models.py:42-58,82-83); destroy leaves orphan Auth user (views.py:141-143); UI toast-only (B5,C-SOP5).
5. [Blocker/S3] ShiftRoster standalone, no FK/date (models.py:62-70); no overlap detection; notifs = hardcoded toast bell (C-SOP3).
6. [High/S4-5] Create-auth-before-validate burns/deletes Auth users; narrow except misses failures (views.py:107-135) — validate local first (B4).
7. [High/S2] Clock-in race (serializers.py:33-41, no atomic → 500 on IntegrityError) + clock-out .get() MultiRow 500, unparsed times (views.py:157-175) (B6,B7).
8. [High/S1] Dashboard unwired: dashboard.js 839 lines zero fetch(; onboarding/offboarding/auth handlers toast-only, static demo data (C1,C2).
9. [Major/S2] net_pay client-writable, never computed; no unique(run,employee); serializers __all__ expose id/status (models.py:80-86; serializers.py) (A,B8).
10. [Med/S2] 502 for all create failures incl. 400s; SQLite hardcoded, UTC/naive drift risk (views.py:128-138; settings.py:91-96,122) (B8,B9).
- Minor backlog: order_by(uuid) random; audit free-text/no actor/purge; /login|signup|/auth same view; modal pattern split.
- Status: A+B+C in. Author may draft CHAPTER3.md from this file. This file is NOT CHAPTER3.md.
