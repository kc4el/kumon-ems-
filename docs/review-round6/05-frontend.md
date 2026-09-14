# Round 6 — Frontend honesty + correctness (static, no server/browser)

Scope: served template `core/templates/core/index.html` (4046 lines — this is what
`core/views.py:72` renders), `static/js/dashboard.js` (1732 lines), `static/css/main.css`.
`node --check static/js/dashboard.js` → **OK**.
`pages/dashboard.html` / `pages/dashboard-preview.html` (3657 lines each, byte-identical
to each other) are **stale mirrors** — see §0. All `core:` lines below are the served file
unless marked `pages:`.

## §0. Served-vs-mirror drift (High for file:// users)

`initBrandLogo` (`JS:59-86`) explicitly supports `file://`, i.e. `pages/` is opened
directly. The mirrors still carry every round-5 bug the served template already fixed:
no `#apiModeBadge`, no `#activityFeed`/`#activityFeedList`, no `#attendanceTableBody` /
`#shiftRosterTableBody` / `#payrollRunsTableBody` / `#payrollLiveWrap`, no `#shortcutHelp`,
**double `<script>` include** (`pages:3653-3654` loads `dashboard.js` twice → all init
loaders fire twice), and all 37 `showToast` call sites. Served template fixed the
double-load with a conditional fallback (`core:4037-4041`). Fix: sync or delete `pages/`.
Severity: **High** (anyone on the mirror gets the pre-fix app).

## §1. Toast-only re-verification (the round-5 originals, checked against served `core:`)

| # | Control | Served status |
|---|---------|---------------|
| 1 | Bell `3 priority employee actions pending.` (`core:105`) | STILL OPEN — toast-only, count is fiction |
| 2 | Roster `+ Assign Roster` → `Roster assignment dialog ready.` (`core:1767`) | STILL OPEN — opens nothing |
| 3 | `confirmAddStaff` → `Assigned … successfully!` (`JS:783`) | STILL OPEN — DOM-only, `POST /api/shift-rosters/` exists (`api/urls.py:106`) but is never called |
| 4 | `removeShiftStaff` → `Employee removed…` (`JS:808`) | STILL OPEN — DOM-only, no DELETE |
| 5 | `handleShiftDateChange` → `Roster updated for …` (`JS:686`) | STILL OPEN — label change only |
| 6–7 | Record Promotion / Transfer success toasts | FIXED in served (`core:1080,1136` now `disabled` + `title`) — but see F3 (no `:disabled` styling) |
| 8–11 | Exit-doc uploads ×4 | FIXED in served (`core:1294-1330` `disabled` + `Attachments aren't connected yet` note) |
| 12 | Exit ✕ `File removed` | FIXED in served (call site gone; served has 28 `showToast`, none for removal) |
| 13–17 | Onboarding uploads ×5 (`core:3936,3946,3957,3967,3978`) | STILL OPEN — `Upload dialog opened for …`, opens nothing |
| 18 | Onboarding Re-upload (`core:3997`) | STILL OPEN |
| 19 | Onboarding ✕ `Contract removed` (`core:3993`) | STILL OPEN — opacity dim only |
| 20–24 | Grievance ×5 (`core:1445,1446,1448,1462,1464`) | STILL OPEN — `Mediation session scheduled.` / `marked as resolved.` / `Approved ergonomics equipment.` / `Contacted vendor…` / `Opened investigation notes…` persist nothing |
| 25 | `handleGrievanceSubmit` → `filed and assigned to HR Mediator` (`JS:638`) | STILL OPEN — **no grievance endpoint exists** in `api/urls.py`; relabel, don't wire |
| 26 | `handleRequestAdvance` → `submitted for HR cap verification` (`JS:963`) | STILL OPEN — **no advance endpoint exists**; same treatment |
| 27 | Attendance `Exported attendance register as CSV.` (`core:1587`) | STILL OPEN — creates no file (only `exportAuditLogs` builds a real download, `JS:1397-1421`) |
| 28 | `Exporting settlement audit history as CSV...` (`core:2755`) | STILL OPEN |
| 29–34 | Receipt/invoice `Downloading …` ×6 (`core:2484,2523,2562,2601,2640,2679`) | STILL OPEN |
| 35 | Chat attachment `Download` (`core:3244`) | STILL OPEN |
| 36–38 | Pagination `Loading page 2/3/next…` (`core:3639-3641`) | STILL OPEN (`<` is honestly `disabled`, `core:3637`) |
| 39–40 | Chat `Search` / `Mute` (`core:3205,3215`) | STILL OPEN |
| 41–42 | Chat attach file/image (`pages:2986,2994` era) | FIXED in served — real `<input type=file>` pickers (`core` composer) feeding `FormData` POST (`JS:1190-1198`); pre-send "attached" toast is honest |
| 43 | `exportAuditLogs` real CSV | HALF-OPEN — download is real but rows are a hardcoded June sample (`JS:1399-1411`) while the filename stamps today; button says `Export Audit CSV` implying current view |
| 44 | `batchApproveClaims` → `Batch approved all…` (`JS:945`) | STILL OPEN + worse: with **zero** pending badges the loop is skipped and the success toast fires anyway — false success on a no-op |

## §2. Tour 12-stop claim accuracy (`JS:342-355` vs served DOM)

| Stop | Verdict |
|------|---------|
| 1 dashboard arrows "jump you straight to the right page" | TRUE (`switchView` targets exist) |
| 2 "Today box shows the latest goings-on" + "badge tells you fresh vs samples" | NOW TRUE — `aside#activityFeed` (`core:148`), `#apiModeBadge` (`core:103`). Was false in round 5 |
| 3 directory + demo `Full staff profiles and chat messaging are on the way soon!` | STALE — expandable live cards (`JS:1504-1534`) and chat send/attach shipped; note must go |
| 4 manage "three tabs … yes-or-no questions files a resignation" | TRUE — tabs + radios (`core:1188-1192`) + real offboard (`JS:532-563`); tour doesn't claim promote/transfer work, so their disabled state is consistent |
| 5 grievance "schedule sit-downs to sort things out" | FALSE — Schedule Mediation is toast-only (§1 #20-24). Demo `Online filing is coming soon` stays TRUE (no endpoint) — keep |
| 6 daily "Use the little arrows to hop between days" | FALSE — the day arrows (`stepShiftDate`) live in the **shift** view (`core:1965-1980`); `view-attendance-daily` has none. Demo `Downloading this as a file is coming soon` also understates the Export button's outright false success (§1 #27) |
| 7 shift "Pick a date (or just press Today), then press Assign" | HALF-FALSE — date/Today are real; **Assign opens nothing** (§1 #2). "Warning flag = approved leave that day" is live-only: `refreshShiftConflictBadges` (`JS:1634-1651`) queries per live row, static board never flags |
| 8 leave "approve or say no … from the same list — they will get a message" | FALSE twice — `#leaveRegisterTableBody` (`core:2255-ish`) has zero approve/reject controls and no messaging is wired |
| 9 claims "approve a whole bunch at once" + demo `More pages are coming soon.` | TRUE — batch approve POSTs (`JS:933-945`, modulo §1 #44); pagination really is dead |
| 10 messages "whatever you send goes out under your own name, automatically" | FALSE — `sender_name` is hardcoded `'Marcus Williams'` (`JS:1192`); anyone else sends under a false name. Identity bug, **High** |
| 11 logs category buttons + demo `More pages are coming soon.` | HALF-FALSE — buttons are wired but **live rows all get `data-category="General"`** (`JS:1716`), a value in neither the pills nor the select (`core:3348-3364`), so any pill click hides every live row; pill counts (`1,482`/`412`/`318`/`286`/`244`/`222`, `core:3321-3326`) never reflect live data |
| 12 "`?` key … Replay button back on the home screen" | NOW TRUE in served — `#shortcutHelp` exists (`core:4017-4035`), Replay injects (`JS:429-445`). Still false on the `pages/` mirrors |

## §3. Placeholder-view copy (`core:3650-3683`)

`Production Module Active` + `This module connects directly with Kumon EMS records and
HR analytics.` renders for `reports`/`profile`/`my-details` (breadcrumb entries with no
sidebar link and no live loader) with **zero** live content — overclaim. And
`loadPayrollView` is unreachable: no UI passes a `payroll*` view name and init never
calls it, so `#payrollLiveWrap` stays `display:none` forever (`core:3666`, `JS:1653-1693`
dead in practice). Severity: **Medium**. Minimum fix: per-view honest copy
("Reports view is not connected yet") or drop the breadcrumb entries.

## §4. Hardcoded demo values shown as live (served)

- **H1 (Medium).** `#shiftDateDisplay` initial text is `Live allocation for Thursday, 18 June 2026` (`core:1961`) — the word **Live** on static demo data. (After any date change it honestly reads `Allocation (demo) for …`, `JS:684`.)
- **H2 (Medium).** `MON, 09 JUNE 2026` (`core:125`) and `Greetings, gurt!` (`core:126`) — date stale, name a placeholder; replace with session user or neutral greeting.
- **H3 (Low).** Navy-box `1,420` / `18` / `32` and `JUNE 2026` tag are static forever; only the global badge discloses. Per-card disclosure missing, same for KPI `116` applicants which `loadDashboardSummary` deliberately skips (`JS:1466`).
- **H4 (Low).** KPI trends `↗ 8.4%` / `↗ 3.2%` / `↗ 2.1%` / `↗ Needs you` (`core` ~`200-241`) never update even on live load.
- **H5 (Low).** Date pin `2026-06-18` (`JS:709`, picker `core:1975`, column `18 Jun • Today`), week nav `June 15 – June 21, 2026`; chat separator `Today, August 28`; log/audit/leave/claims rows all June/Aug-2026 static.
- **H6 (Medium).** `Showing ${visibleCount} of 1,482 logged admin events` (`JS:1393`) + pill counts (§2 stop 11) + initial `Showing 1 to 10 of 1,482` — denominator fiction regardless of live row count.
- **H7 (Low).** `+ Batch Approve (0)` (`core:2448`) never reflects pending count.
- **H8 (Medium).** Static Sarah-Chen demo thread + PDF card persist above live messages with no disclosure; loader only clears `[data-persisted-message]` (`JS:1131`).
- **H9 (Low).** Leave mini-KPIs `02`/`01`/`14`/`3.2 Days` (`core:1408-1423`), shift mini-KPIs (`core:1560-1575`), inbox timestamps/snippets/`Online Now`, `unread-count-pill` — all static.
- **H10 (Low).** Leave-modal applicant list (4 static names) may miss the live directory → submit dead-ends at `Applicant is not in the live employee directory yet.` (`JS:990`); advance-modal salaries (`$8,500/mo`…) static; avatar hardcodes `MW • Marcus Williams`.

## §5. escapeHtml gaps (`JS:1218-1220` covers `&<>"'`)

- **E1 (Low, real).** `confirmAddStaff`: `select.value.split('|')` destructured into `escapeHtml(initials/name/jobTitle)` (`JS:747-762`); a malformed option makes them `undefined` → `escapeHtml(undefined)` **throws** (`str.replace` of undefined), uncaught, click dies silently. Not triggerable today (all `staffSelect-*` options are well-formed 3-part, `core:2021+`) — harden with `String(x || '')`.
- **E2–E3 (verified, no gap).** `messageOnSlack(this.dataset.name)` interpolation is quote-escaped (`JS:1531`); expanded-card bodies escape name/role/email (`JS:1519-1531`).
- **E4 (Low).** `messageOnSlack` matches by **first-name substring** against tile text (`JS:1096-1098`): `Marcus Williams`/`James O'Brien` static cards (`core:605,790`) match no tile → fallback toast (honest); duplicate first names would message the wrong person; empty input matches the first tile always. Correctness only — sinks are `textContent`/comparison, no XSS.
- Rest verified safe: chat + toasts + tour use `textContent`/`createElement` (incl. `file.name`, `JS:1177`); feed/shift/attendance/roster/payroll/audit interpolations escaped (`JS:333,759-762,1516-32,1588-93,1620-25,1678-82,1718-24`); payroll `is_processed`/`lines.length`/`toFixed` are boolean/number-safe; breadcrumb map is static (`JS:184-186`); `dataset.*`/`placeholder` assignments are DOM-safe, not HTML sinks.

## §6. Breakpoints — hero + new layout (`main.css`)

- **B1 (OK).** `≤1200px`: hero → 1 col, split → 1 col, KPI → 2 col, messages → 1 col (`CSS:3825-3838`); `≤768px`: sidebar stacks, nav scrolls, KPI → 1 col (`CSS:3840-3865`); tour bubble `calc(100vw-48px)` (`CSS:3874`); hero children `min-width:0`, summary boxes `flex:1 1 0`, `flex-direction:column ≤768px` (`CSS:3882-3890`). Summary-side staying 2-up between 769–1200px is reasonable.
- **B2 (Medium).** `.inputs-3grid` (3 col), `.inputs-split-3grid` (`180px+200px+1fr`), `.inputs-split-grid` (`240px+1fr`), `.inputs-2grid`, `.docs-compliance-grid`, `.compliance-2col-grid` (`CSS:1082-1130,1359,1659`) **never collapse** at any breakpoint; with `body{overflow-x:hidden}` (`CSS:68`) the transfer form and modal 2-col grids clip past ~400px instead of scrolling. Add a `≤768px` single-column rule.
- **B3 (Low).** `.hero-heading` fixed `38px` (`CSS:379-386`), no `clamp()` — fine for current copy at 360px, will overflow with a real long name (see H2).
- **B4 (Low).** `#activityFeed{min-height:182px}` (`CSS:3886`) vs navy-box content height is eyeball-matched, unverifiable statically; base `float:right;width:300px` (`CSS:3869`) is correctly overridden inside the hero flex row (`CSS:3889`, higher specificity) — no bug, noting so nobody "fixes" it.
- Tables/containers verified wrapped: `.shift-calendar-container{overflow-x:auto}` (`CSS:2243-2244`), claims wrapper (`CSS:2612-2613`), audit card `overflow:hidden` + inner scroll (`core` logs card) — no page-level overflow expected from tables.

## §7. Dead buttons introduced by recent (T1–T8-era) changes

- **F1 (Medium).** Static directory `View Full Profile` buttons have **no handler at all** (`core:511,604,696,789,881` — bare `class="btn btn-black-sm"`); live-rendered ones `onclick="switchView('employee-directory')"` (`JS:1530`) — a self-loop no-op. Either wire to expand the card or remove.
- **F2 (Low).** Chat `View Profile` → `switchView('employee-directory')` (`core` chat header) lands on the directory top, not the person — misleading label; route to `messageOnSlack`-style lookup or relabel.
- **F3 (Medium).** The three honest `disabled` fixes (§1 #6-12) ship with **zero `:disabled` styling** — no `:disabled`/`[disabled]` selector exists in `main.css` — so dead buttons look fully clickable. Add a dimmed `cursor:not-allowed` rule.
- **F4 (Low).** `#chatTextInput` is `required`, which natively blocks the file-only send that `handleSendChatMessage` explicitly supports (`JS:1187`); remove `required` and keep the JS guard.
- **F5 (Medium).** `showToast(message)` (`JS:841`) still single-arg; the typed fallback (`JS:1429-1449`) never installs (function declaration hoists), so all ~10 `showToast(msg,'error')` failure toasts render identically to info — error styling is dead. Fold `type` into the primary definition.
- **F6 (Low).** `deptFilter`/`roleFilter` use exact match (`JS:469-490`) against live `data-dept`/`data-role` (`JS:1510-1511`); any live name outside the six static options (e.g. a real `Product` dept) becomes unfilterable/hidden on select. Consider `all`-default-safe contains-match or syncing options from `/api/departments/`.
