# Remaining employee workflows

This change completes the verified missing application workflows. It does not edit the research paper, replace the Django interfaces, introduce pay disbursement, or change post-resignation erasure and cloud availability/synchronization.

## Employee and HR requests

- Employees can view their assigned schedules and request a same-date shift swap with another eligible employee. The target employee or HR can decide the request. Approval exchanges assignments atomically and rejects overlapping shifts.
- Swap participants are saved independently of roster ownership, preserving access boundaries after a swap. Pending requests prevent HR from changing the affected rosters.
- Legacy swaps without saved participant identities remain visible only to HR. HR must reject pending legacy requests and ask employees to create new ones; the application does not guess historical participants.
- Employees can submit attendance corrections and overtime requests from their attendance history. HR reviews them in the attendance workspace. Only HR approval applies a correction.
- Overtime hours and multipliers come from the effective Pay Estimate policy and scheduled breaks. Missing configuration, ambiguous partial shifts, and overnight attendance require manual review. These requests support advisory Pay Estimates, not payment processing.

## Messaging and notifications

Both employee and HR interfaces support message attachments. Uploads must be nonempty PDF, JPEG, PNG, or UTF-8 text files no larger than 5 MB, with basic content checks. Downloads require conversation access and use a private authenticated endpoint. Direct development-media access to message attachments is blocked. A production web server must likewise keep this storage private rather than expose its media directory directly.

Notification invalidation uses authenticated server-sent events. The server checks recipient-scoped notification state every two seconds, sends no message text in events, and reconnects after short streams. Existing polling remains a fallback. This is near-live application notification delivery; it is not cloud database synchronization or a high-availability guarantee.

## Attendance and retired features

The legacy password-only attendance endpoint is disabled. Employee attendance writes require the canonical QR/manual-code flow, including active onboarding/account checks and the mobile-check-in setting. HR alone can display live QR tokens. Token consumption and attendance updates share a transaction, with conditional token consumption and row locks where supported. Manual attendance edits remain HR-only and audited.

Performance-review models, serializers, signals, and API routes have been retired. Migration 0041 removes the model from Django state while preserving the historical database table. Migration 0042 adds saved swap participants. Apply pending migrations before running this version; migrations were not applied to the application database during this change.

## Validation

- Six focused staff-request tests passed before the later participant-identity and locking refinements.
- Four attachment/notification tests and four performance-retirement tests passed.
- Final Python AST parsing, JavaScript syntax checks, and diff checks are recorded with the change. These are static checks, not runtime verification.
- Additional participant-privacy, onboarding, QR authorization, concurrency, and legacy-contract tests are included. Their final combined run is unverified: automatic approval review stopped the attendance-security test run after detecting unverified Visual Studio telemetry traffic. The blocked run was not retried.
- Browser automation was not used, in accordance with this repository's testing instructions. No claim of full runtime or browser validation is made.

Changes are local and have not been pushed to the remote repository.
