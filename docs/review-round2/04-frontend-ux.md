# Review Round 2 — 04 Frontend & UX (dashboard.js @1027 lines, index.html @4061)

## Live vs static demo (verified changed since round-1)
- LIVE: KPI cards 0/2/3 via `GET /api/dashboard-summary/` — `dashboard.js:951-973`. [info]
- LIVE: employee directory re-rendered from `GET /api/employees/` — `dashboard.js:980-1025`. [info]
- LIVE: onboarding `POST /api/employees/` (`:258-287`) and leave `POST /api/leaves/` (`:601-635`). [info]
- STATIC: hero pulse stats (1,420 / 18 / 32 / 94.2%) hardcoded — `index.html:~145-200`; KPI slot 1 (applicants) deliberately untouched — `dashboard.js:963`. [med]
- STATIC: attendance-daily/shift views, claims approve/batch (`dashboard.js:520-554`, DOM+toast only), advance request (`:568-573`, toast only), inbox (channel switch hardcodes "Company Announcements", `:650-667`; send appends locally, `:691-716`), audit filter/export with hardcoded CSV rows (`:861-920`), offboarding/promote/transfer/grievance (toast only, `:217-220`, `:289-294`; `index.html:1114,1170`), payroll+reports have no view → generic placeholder (`index.html:3698-3700`). [med]

## Demo-fallback confusion (highest UX risk)
- Summary/dir fetch failures silently keep demo values/cards, no offline/demo badge — `dashboard.js:970-972,1022-1024`. User cannot tell live from fake. [high]
- `handleShiftDateChange` labels purely local date switch "Live allocation for …" — `dashboard.js:336-340`; roster confirm sets badge "Confirmed" with no POST — `:424-429`. [high]

## Loading / empty / error states
- No spinners/skeletons or empty-state on either GET path; zero-employee response renders blank list (`list.innerHTML=''` then append loop, `:995`). [med]
- POST errors surface as toasts only, no inline field errors; no disable-while-pending → double-submit possible (`:247-287`, `:586-635`). [low]

## 403 → login, post-login return
- 403 redirects to `/login/` with no `?next=` — return destination lost — `dashboard.js:264-266,613-615,985-987`. Summary path ignores 403 entirely (falls into demo fallback, `:952-956`). [med]
- Login/signup still toast + `sessionStorage` only, no `api/auth-token`/session call — `dashboard.js:760-818,764,794`; prefilled demo creds `EMP-10482/kumon2026` — `login.html:44,51`; `signOut` only clears storage — `dashboard.js:831-838`. [high]

## Modals
- Inconsistent pattern: leave/advance use `.active` class (`:558-584`, CSS `main.css:2012`) but onboarding uses inline `style.display` (`:223-237`, `index.html:3821`) against a conflicting duplicate `.modal-backdrop` def (`main.css:1507` flex vs `:1998` none). [med]
- Only onboarding has Escape (`:240-244`) and click-outside (`index.html:3821-3822`); leave/advance lack both; no focus trap anywhere. [low]

## Validation
- HTML `required`/`min`/`max` only (leave `index.html:3732-3762`, advance `:3782-3808`, onboarding `:3842-3881`); JS splits full name naively (empty `first_name` possible, `:250-257`); leave skips end<start check; advance has zero JS validation. [med]

## XSS
- `escapeHtml` (`dashboard.js:718-720`) correctly covers chat (`:706`) and directory name/role/email (`:1011-1012`). [info]
- GAP: `confirmAddStaff` interpolates select-derived name/jobTitle/role into `innerHTML` unescaped — `:411-420`. [med] Others (`:539,551`, breadcrumb `:127-130`) use static strings — safe. [info]

## Toast + responsive
- `showToast` has no definition except the `window.showToast` fallback (`:926-947`), which creates a second `#liveToast` node; `index.html:4051` `#toastContainer` is never written to. [low]
- Responsive basics OK: viewport (`index.html:7`), breakpoints stack hero/KPI/messages/sidebar (`main.css:3705-3740`), tables have `overflow-x` wrappers (`:2119,2487`). No obvious mobile breakage found. [info]
