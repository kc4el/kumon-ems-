# Employee DIRECTORY view review

Scope: `core/templates/core/index.html` lines 353–985 (`#view-employee-directory`,
`#employeeRosterList`); `static/js/dashboard.js` `toggleAccordion` (~447),
`filterDirectory` (~466), `loadEmployeeDirectory` (~1457), `liveEmployeeNames` (~1507).
Init call: `dashboard.js:10` (`loadEmployeeDirectory()` on `DOMContentLoaded`).
Auth/transport: `dashboard.js:28` (`apiFetch`, session cookies + CSRF);
mode badge: `dashboard.js:48` (`setApiMode`); no search input exists anywhere
inside `index.html:353–985`.

## Working (live)

- Directory boots live: `dashboard.js:10` calls `loadEmployeeDirectory()`, which
  `GET`s `/api/employees/` with `Accept: application/json` (`dashboard.js:1460`).
- Live rows replace demo markup: `list.innerHTML = ''` then one card per API row
  (`dashboard.js:1468`), with `data-live="true"` (`dashboard.js:1474`),
  `data-dept` from `emp.department_name` (`dashboard.js:1475`), `data-role` from
  `emp.role` (`dashboard.js:1476`), name from `first_name + last_name`
  (`dashboard.js:1470`), role/email line from `emp.role` / `emp.email`
  (`dashboard.js:1485`), XSS-escaped via `escapeHtml` (`dashboard.js:1190`).
- Status mapping is live-derived: `is_active === false → 'On Leave'` else
  `'Present Today'` in `data-status` (`dashboard.js:1477–1480`), badge class
  `badge-leave` / `badge-present` (`dashboard.js:1488`).
- Dept/role/status filters work on both demo and live cards because
  `filterDirectory()` reads the `data-*` attributes case-insensitively and
  `display:block/none`s non-matches (`dashboard.js:467–488`), wired via
  `onchange="filterDirectory()"` on `#deptFilter` (`index.html:397`),
  `#roleFilter` (`index.html:406`), `#statusFilter` (`index.html:415`); live
  loader re-applies it after render (`dashboard.js:1493`).
- Accordion expand/collapse works (pure CSS-class toggle + chevron/label swap,
  no network): `toggleAccordion` toggles `.open` (`dashboard.js:448–463`),
  wired via `onclick="toggleAccordion(this)"` on every demo summary
  (e.g. `index.html:428,521,613,706,798,890`).
- Failure falls back visibly: catch sets DEMO badge (`dashboard.js:1497`) and
  toasts `API unreachable — showing demo data` (`dashboard.js:1498`), leaving
  the 6 demo cards in place; auth redirects are skipped silently
  (`dashboard.js:1496`). Success sets LIVE badge (`dashboard.js:1466`).
- New hires appear: onboarding POST success calls `loadEmployeeDirectory()`
  (`dashboard.js:612`), re-rendering the roster from the API.
- Name index is live: `loadEmployeeDirectory` fills `employeeNameIndex`
  (lowercased full name → id, `dashboard.js:1471`) for the leave-modal lookup;
  `liveEmployeeNames()` separately caches `id → display name` from
  `/api/employees/?page_size=50` (`dashboard.js:1507–1518`).

## Static / unwired

- All 6 demo profile bodies are hardcoded with no fetch: Sarah Chen
  (`index.html:426–516`), Marcus Williams (`index.html:519–609`), Priya Patel
  (`index.html:612–701`), James O'Brien (`index.html:704–794`), Elena Rodriguez
  (`index.html:797–886`), David Kim (`index.html:889–978`) — emails
  (e.g. `index.html:462,555,647,740,832,924`), phones `+1 (555) …`
  (e.g. `index.html:470,563,655,748,840,932`), locations (`index.html:479,572,
  664,757,849,941`), hire dates (`index.html:494,587,679,772,864,956`), grades
  L4–L6 (`index.html:503,596,688,781,873,965`), performance strings
  (`index.html:508,601,693,786,878,970`).
- Filter option lists are hardcoded, not derived from data: 6 depts + All
  (`index.html:397–405`), 6 roles + All (`index.html:406–414`), 3 statuses + All
  (`index.html:415–420`); no other dept/role/status value is selectable, and
  Sales (`index.html:400`) has zero demo cards.
- Status vocabulary is inconsistent: filter/cards use `Present Today /
  Probation / On Leave` (`index.html:415–420`, `data-status` at
  `index.html:426–427,519–520,612,704–705,797,889`), but live cards render badge
  text `Inactive / Active` (`dashboard.js:1488–1489`) while keeping `data-status`
  `On Leave / Present Today` (`dashboard.js:1477–1480`) — badge text and filter
  value disagree, and live data can never produce `Probation`
  (`dashboard.js:1477–1480` maps only on `is_active`).
- Live cards are summary-only, strictly less than demo: `card.innerHTML` builds
  only `.acc-summary` (name + role/email + badge, `dashboard.js:1481–1490`) —
  no `.acc-expanded-body`, no contact/phone/location/date/grade/performance, no
  toggle tag — so clicking a live row toggles `.open` with nothing to reveal.
- `View Full Profile` buttons (6×: `index.html:510,603,695,788,880,972`) and
  `Message on Slack` buttons (6×: `index.html:511,604,696,789,881,973`) have no
  `onclick`, no id, and no matching handler in `dashboard.js` (only
  `apiFetch`/`setApiMode`/`showToast`/`escapeHtml` exist at
  `dashboard.js:28,48,823,1190`; no profile/Slack function) — both are dead.
  Live cards omit both buttons entirely (`dashboard.js:1481–1490`).
- No directory search box: nothing matching search exists in
  `index.html:353–985` (only the three selects at
  `index.html:397,406,415`).
- No pagination: no page buttons/count inside `index.html:353–985` (the only
  pagination bars in the file are claims/audit at e.g. `index.html:2721,2926,
  3111,3652–3659`, none for the roster); live fetch takes only the first page
  (`/api/employees/` with no `page_size` at `dashboard.js:1460`, vs
  `?page_size=50` used by `liveEmployeeNames` at `dashboard.js:1509`).
- No loading state: `loadEmployeeDirectory` never writes a spinner/skeleton into
  `#employeeRosterList` (`dashboard.js:1457–1500`), unlike
  `loadAttendanceView` which writes `Loading…` (`dashboard.js:1530`).
- No empty state: on zero rows the loader leaves `list.innerHTML = ''` with no
  `No employees` message (`dashboard.js:1467–1468`), unlike attendance's
  `No records yet` (`dashboard.js:1539–1540`).
- No error placeholder in-DOM: the catch path only toasts + badge
  (`dashboard.js:1497–1498`); a roster that fails before first paint shows
  whatever markup was there with no inline error.
- Probation/On-Leave demo badges are static text (`badge-probation` at
  `index.html:627`, `badge-leave` at `index.html:904`) with no attendance/leave
  source behind them — accepted static-demo posture, noted only for completeness.

## Missing vs a real HR directory

- Search by name/email/role (no input in `index.html:353–985`).
- Pagination / result count (`Showing N of M`); related precedent exists only
  for audit logs (`dashboard.js:1363–1365`).
- Loading, empty, and inline-error states for the roster
  (`dashboard.js:1457–1500` has none; cf. `dashboard.js:1530,1539–1540`).
- Full profile surface: detail page/modal, reporting line, manager, emergency
  contact, documents, tenure/leave balances — `View Full Profile` dead
  (`index.html:510` et al.), live cards body-less (`dashboard.js:1481–1490`).
- Contact actions: `Message on Slack` dead (`index.html:511` et al.); no
  `mailto:`/`tel:` links on the listed emails/phones
  (`index.html:462,470` et al. are plain `<span>`).
- Filter options derived from live data; current hardcoded lists
  (`index.html:397–420`) drift from API values (`department_name`/`role` at
  `dashboard.js:1475–1476`).
- Consistent status vocabulary end-to-end (filter `index.html:415–420` vs live
  badge `dashboard.js:1488–1489` vs live `data-status`
  `dashboard.js:1477–1480`).
- Photo/avatar, team/org-chart grouping, export (CSV/vCard) — none present in
  `index.html:353–985`.

## Suggested fixes (narrowest first)

1. Unify the live status words: render badge text from the same
   `Present Today / On Leave` strings written to `data-status`
   (`dashboard.js:1477–1489`), so the badge matches `#statusFilter` options
   (`index.html:415–420`).
2. Give live cards the expandable body: include `.acc-expanded-body` with
   email/department (fields already fetched at `dashboard.js:1475,1485`) so
   `toggleAccordion` (`dashboard.js:448–463`) has content on live rows.
3. Add roster loading/empty rows mirroring attendance (`dashboard.js:1530,
   1539–1540`): `Loading…` on entry, `No employees match these filters.` when
   rows or visible cards are zero.
4. Wire or remove dead buttons: either bind `View Full Profile` /
   `Message on Slack` (`index.html:510–511` et al.) to a profile modal /
   `mailto:` link, or delete them from demo markup and stop rendering them.
5. Add `?page_size=` + result count to `loadEmployeeDirectory`
   (`dashboard.js:1460`) consistent with `liveEmployeeNames`
   (`dashboard.js:1509`) and the audit counter (`dashboard.js:1363–1365`).
6. Add a name/email filter input beside `#deptFilter` (`index.html:397`) that
   extends `filterDirectory` (`dashboard.js:467–488`) to match `.acc-name` text.
