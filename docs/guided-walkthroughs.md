# HR and employee guided walkthroughs

The merged system's six-step HR tour has been replaced by a shared navigation-only guide. Both portals have **Help**, a short introduction, and optional task guides. HR's existing **Take a quick tour** button replays the introduction through a single event handler.

## Coverage

HR guides cover employee records, attendance/corrections/overtime, scheduling/swaps, leave requests and allocations, claims/advances, complaints/grievances, advisory Pay Estimates, messages, activity logs, and account settings. Employee guides cover attendance, leave/balances, advances, expense claims, schedules/swaps, corrections/overtime, concerns, messages/notifications, and account security. Claims are explicitly identified as part of Requests & notifications. Estimates are described as HR advisory review aids, not payment authorization. Google linking is described as optional and separate from configurable authenticator verification.

The engine navigates views and existing display tabs only. It does not submit forms, approve requests, create estimates, change entitlements, generate QR tokens, or enable security settings on the user's behalf. Normal application reads still occur when a view opens. Pending or unsaved forms prevent a guide from starting; typing into a form dismisses an active guide without clearing its inputs. Schedule date filters are excluded from dirty-form tracking. A nonmodal guide card leaves ordinary keyboard navigation available; Escape closes it. The card returns focus to its launcher when appropriate without stealing focus from a user who begins editing.

## Progress and readiness

Progress is stored by tutorial version, account, portal, and task in the current browser. Dismissed and completed are distinct states; replay is always available. Changing accounts or switching HR/employee portals does not reuse another account's completion state. This is browser-local, not server-synchronized progress. If localStorage is blocked, the current page uses an in-memory fallback.

A first-use invitation offers Start introduction or Not now; it never automatically navigates away. Guide steps await dynamically generated controls and check visibility. Missing controls display a recoverable message; a tour containing missing steps is not marked fully completed. Stale asynchronous steps cannot reopen a closed guide. Target highlighting and card positioning respond to scrolling, resize, and visual viewport resizing. Cards have bounded widths/heights for small screens and respect reduced-motion navigation for their own scrolling.

## Supporting profile corrections

The employee profile's sample leave totals have been replaced with a link to the actual balance display in Leave Requests. Document fixtures and unsupported VERIFIED/ACKNOWLEDGED claims have been removed. The profile now loads that employee's actual onboarding-document records, handles empty/error states, and links to authenticated download routes. A document's presence is not described as verification. The profile uses the assigned employee ID and recorded status instead of a shortened UUID and fixed Full-Time label; fake contact details and hire-date fallbacks have been removed.

No database migration is required by this update.

## Validation

`node --test tests/guided-tour.test.cjs` covers account/portal isolation, private-storage fallback, dismiss/finish/replay, back navigation, unsaved-form protection, out-of-order asynchronous navigation, cancellation, missing targets, viewport placement, delayed targets, abort/timeout cleanup, and static target contracts. JavaScript syntax checks also passed.

The existing local preview returned cached older templates when checked over HTTP. Restart the Python process started by `Start-Kumon-EMS.cmd` before using this update. The full interactive walkthrough and visual phone layout have not been browser-tested; browser automation is excluded by this repository's testing instructions. These unit/source checks do not establish a full user-interface acceptance test.

Changes are on a new branch based on the merged main version. They have not been published or merged into main by this implementation task.
