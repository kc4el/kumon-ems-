# IDEAS-D — UX / Productivity Features

Scope: chore/standard-format @ 81046d1; vanilla-JS dashboard, no roles. Excludes B3 role-views + B1 CSV export.

## D1. Global command search (Ctrl+K)
- Problem: HR hunts across tabs to find one employee, leave, or shift.
- Proposal: `Ctrl+K` palette searching employees/leaves/shifts by name/date; Enter jumps to row/tab.
Client-side index over already-fetched lists, no new endpoint.
- Value: single fastest daily time-saver for lookups.
- Effort: S

## D2. Bulk approve / reject actions
- Problem: leave/attendance approved one row at a time during peak periods.
- Proposal: checkboxes + "Approve all selected" bar; one batched `POST` with id list, per-row failure summary.
- Value: cuts peak-season approval clicks from N to 1.
- Effort: S

## D3. Saved filters / views
- Problem: HR re-applies the same filters (e.g. "pending leaves", "this-week absences") daily.
- Proposal: "Save current filter" button storing label+query in `localStorage`; dropdown restores it.
Server-side persistence later; start local-only.
- Value: one-click repeat of common daily queries.
- Effort: S

## D4. Keyboard shortcuts + shortcut help
- Problem: all actions are mouse-only; power users re-click through tabs.
- Proposal: `g+d/l/a/p` tab jumps, `a/r` approve/reject on focused row, `?` opens cheat sheet.
Shortcuts listed in help modal; respect focus-in-input guard.
- Value: keyboard-first HR clears queues noticeably faster.
- Effort: S

## D5. Customizable dashboard widgets
- Problem: fixed dashboard shows same cards to everyone regardless of daily focus.
- Proposal: show/hide/reorder cards (approvals, headcount, today's shifts) in `localStorage`. Same data as B3, personal order.
- Value: each HR sees their morning priorities first.
- Effort: M

## D6. Team activity feed
- Problem: no shared view of "what changed today" across HR staff.
- Proposal: "Today" sidebar listing recent approvals, new hires, shift changes (human-readable,
not B2 audit viewer nor A2 personal inbox). Backed by existing timestamps.
- Value: shift-handover context without asking around.
- Effort: S

## D7. Email + push delivery for notifications
- Problem: A2 notifications are in-app only; approvers miss urgent requests off-screen.
- Proposal: opt-in email digest + Web Push on leave/shift decisions via service worker;
preferences toggle per user.
- Value: urgent approvals reach approvers off-dashboard.
- Effort: M / Depends-On: A2 notification model

## D8. Dark mode
- Problem: bright-only dashboard strains eyes during long roster/payroll sessions.
- Proposal: CSS-variable theme + header toggle persisted in `localStorage`; default light.
No backend change.
- Value: comfort + after-hours usability for near-zero cost.
- Effort: S

## D9. Tagalog / English toggle
- Problem: some staff struggle with English-only labels and leave reasons.
- Proposal: `tl`/`en` dictionary for nav, buttons, headers; header toggle in `localStorage`. Data values untranslated.
- Value: wider staff adoption without retraining.
- Effort: M

## D10. Guided onboarding tour
- Problem: new HR users face 10+ tabs with no guidance on daily flow.
- Proposal: 5-step first-run tour (dashboard → leaves → roster → payroll) with skip/replay;
pure JS overlay, no backend.
- Value: new staff productive on day one without hand-holding.
- Effort: S
