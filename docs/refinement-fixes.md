# Portal and request integrity fixes

This update addresses the twelve confirmed findings reviewed against c7165a2.

- Leave and advance records retain their employee owner. Pending requests can be edited or deleted; decided requests are immutable. Decisions lock rows in a transaction, allow identical replays, and reject conflicting decisions. Bulk leave decisions validate every requested row before writing. Leave quotas and balance policy are unchanged.
- Excel imports now use the same local account provisioning as individual onboarding. Successful rows receive linked accounts, employee IDs, and expiring credentials. HR can reveal or copy each employee's credentials in the import results, then clear them. Credentials are not saved in browser settings and API responses prohibit caching. Previously imported records are not automatically backfilled.
- Impossible hire dates return validation errors. Password changes update the current session hash while revoking other sessions and tokens.
- Case review drafts survive polling, tab switches, and edits made during a save. Stale reads cannot replace newer results.
- Employee request histories follow all pagination links. Failed refreshes retain existing data and show Retry. Attendance controls remain disabled when attendance status cannot be verified.
- Notification badges use a recipient-scoped unread-count endpoint with the same mute filters as the inbox.
- Successful preferences saves clear the guide's unsaved-form state; failed saves and edits made during a request remain protected.
- QR event streams unregister on closure, and subscriber queues have a bounded, nonblocking backlog.

## Verification

25 standalone Node tests and seven isolated Python tests passed. All 134 Python files in the application and test directories parsed successfully; modified JavaScript and inline template scripts passed syntax validation. Whitespace checks passed.

Django integration regression tests were added for account sessions, notification counts, provisioning, and request integrity, but were not executed. Browser automation and live database checks were not performed. No database migration is required by these changes.

## Second wave

- The HR file and image pickers now replace one another, so the preview and submitted attachment agree. An invalid selection removes the stale preview.
- Send completion remains scoped to the submitted conversation in both portals. A response cannot erase a newer draft or update another conversation's stream or read marker. Overlapping sends are suppressed.
- Company settings validate the complete batch before writing and commit settings and audit rows atomically.
- Overtime approval recalculates current attendance, schedule, and policy values under row locks. Changed or ineligible values block approval. HR can use Recalculate hours to update a pending request, inspect it, then approve or reject it. This does not change pay estimate calculations.

Six isolated messaging tests and five isolated backend tests cover these fixes. Database integration tests were added for overtime recalculation and atomic settings; they remain unrun under the same runtime verification restriction. No migration is required.
