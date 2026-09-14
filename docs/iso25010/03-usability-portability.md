# ISO/IEC 25010 — 03 Usability, Portability

Scope: PR branch `chore/standard-format` (Django 6.1 + DRF, vanilla JS). No code changes.

## 1. Usability

| Sub-characteristic | Verdict | Evidence |
|---|---|---|
| Appropriateness recognisability | PARTIAL | LIVE/DEMO badge now loud: `setApiMode` (`static/js/dashboard.js:34-42`), badge default DEMO (`core/templates/core/index.html:103`), fail-loud toasts (`dashboard.js:1142-1146,1192-1196`); shift label honest `Allocation (demo)` (`:367`), badge `Draft` (`:457`). Residual: applicants KPI deliberately demo (`:1135`), roster/audit/inbox/offboarding/payroll still toast-only/hardcoded (`COMPILED.md` F10). |
| Learnability | PARTIAL | Demo creds prefilled (`pages/login.html:42,49`, `core/templates/core/login.html:44,51`); login/signup retitle (`dashboard.js:909,916`); real `POST /api/session-login/` + `?next=` return (`:933-960`). Drag: signup still toast-only + timed redirect (`:963-990`); no tour/help/empty-states; zero-employee renders blank (`COMPILED.md` F4). |
| Operability | PARTIAL | `apiFetch` sends CSRF + `403→/login/?next=` (`dashboard.js:22-32`); real logout (`:1003-1008`); claims now live (`:566-600`); paginated lists (`settings.py:185-186`). Drag: onboarding uses inline `style.display` (`:257-266`) vs leave/advance `.active` (`:633-659`); duplicate `.modal-backdrop` (`main.css:1513` vs `:2004`); Escape only onboarding (`dashboard.js:274-276`); no focus trap, no disable-while-pending. |
| User error protection | PARTIAL | HTML `required`/date inputs; leave applicant-not-in-directory guard (`dashboard.js:672-675`); API errors as toasts (`:296-304,686-704`); empty-assign guard + focus (`:424-428`). Gaps: naive name split, empty `first_name` possible (`:286-289`); no client end<start check; advance zero JS validation (`:643-648`); no double-submit guard. |
| UI aesthetics | PASS | LIVE green / DEMO amber badge, consistent toast stack (`dashboard.js:524-541`, fallback `:1098-1118`); viewport + breakpoints (`main.css:3706-3735`), `overflow-x` tables. Minor: dual toast defs, duplicate modal CSS above — cosmetic only. |
| Accessibility | FAIL | Zero `aria-live`/`role=status|alert`; no i18n (only `LANGUAGE_CODE` in `kumon_ems/settings.py:138`); `aria-label` only on shift controls (`pages/dashboard.html:1729-1901`); no focus trap/skip-link; toasts not announced. Responsive OK (viewport `pages/dashboard.html:6`, login `login.html:6`). |

## 2. Portability

| Sub-characteristic | Verdict | Evidence |
|---|---|---|
| Adaptability | PARTIAL | Zero-config SQLite default, Postgres when `DB_HOST` set (`kumon_ems/settings.py:95-114`); hosts via env (`:36-42`); CORS localhost-only (`:167-174`). Capped by hard Supabase import (`core/supabase_client.py:13-14` raises) — app cannot boot/adapt without Supabase keys even on SQLite. |
| Installability | PARTIAL | `.venv` + `requirements.txt` incl. `psycopg2-binary==2.9.13` (`requirements.txt:6`); `migrate`/`runserver` (`README.md:74-75`); Windows scheduler noted (`README.md:41`). Drag: README pip line omits psycopg2 + versions (`README.md:52`); no `.env.example` in package; manual SECRET_KEY/SUPABASE/DB_* burden; activate uses unix-only `source .venv/bin/activate` (`README.md:51`). |
| Replaceability | PARTIAL | DB layer clean Django ORM (SQLite↔Postgres swap = env only). Auth provider not replaceable: employee create hard-calls `supabase.auth.admin.create_user` + compensating `delete_user` (`core/views.py:131,154`), 502 without it; no auth-backend abstraction. DRF session+token otherwise standard (`settings.py:178-184`, `api/urls.py:102-104`). |
