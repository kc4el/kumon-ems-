# 03 — Frontend Bugs (round 4, NEW only vs round-3 04/COMPILED)

`node --check static/js/dashboard.js` → exit 0. Round-3 items verified FIXED
(claims/messages now via `apiFetch`, 401+403 redirect, signup real POST,
render paths escaped) and are NOT repeated below. Colspans verified OK
(5/5/4/7); all 12 tour views exist as panels; tour/widget CSS present.

## Findings (all in `static/js/dashboard.js` unless noted)

1. [HIGH] Stored-XSS via unvalidated `attachment_url` → `link.href`
   (`dashboard.js:1131-1136`). Label uses `textContent` but `href` accepts
   `javascript:` from server payload. Validate scheme / same-origin first.
2. [HIGH] `escapeHtml` throws on non-string (`dashboard.js:1190-1192`).
   `confirmAddStaff` passes raw split parts (`:741-744`); a value without
   `|` yields `undefined` → TypeError kills the whole assignment. Coerce.
3. [MED] Tour double-start: `startTour` (`:357-360`) has no running-guard;
   auto-start timer (`:444`) races a manual Replay click → progress reset.
4. [MED] Esc conflict: two independent listeners — `:211` (ends tour) and
   `:573-577` (closes onboarding modal) both fire; advance/leave modals
   (`:932-958`) ignore Esc entirely. One Esc handler, per-modal stack.
5. [MED] Auth-bounce toasts: offboarding (`:550-552`), claim actions
   (`:899-928`) lack the `err.message==='auth'` guard used at `:1446,1496`,
   so a login redirect also flashes a bogus error toast.
6. [MED] Badge race: 6 parallel loaders each call `setApiMode`
   (`:1432,1466,1555,1587,1644,1686`) — last finisher wins; feed (`:324`)
   never touches the badge, so LIVE can show over failed summary.
7. [MED] Widget prefs corruption: `hidden` not Array-validated (`:247-253`,
   crafted string → `.forEach` crash); `dataset.widget` derived from card
   text (`:231-236`) collides on duplicates; new cards fall outside saved
   order (`:242`). Validate entries, key by stable id.
8. [MED] `liveEmployeeNameCache` has no in-flight dedup (`:1506-1518`):
   attendance+shift+audit on one load fire 3× `/api/employees/` in parallel.
9. [MED] Feed shape bug: `rows = payload.results || payload` (`:331`) — an
   error-envelope object renders "No activity yet today" instead of
   "unavailable". Require `Array.isArray`.
10. [LOW] Tour bubble: no focus trap/restore, no `aria-modal` (`:374-428`);
    Tab leaves the dialog into the live background. Trap + restore focus.
11. [LOW] Dead code: `#mentionPicker` absent from `index.html`, so
    `toggleMentionPicker`/`insertMention` (`:1014-1035`) can never trigger.
12. [LOW] Esc/`?` while typing in inputs early-returns (`:209`), so an open
    shortcut-help panel or tour can't be Esc-dismissed from chat input.
