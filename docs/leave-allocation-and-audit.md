# Leave allocations and audit actors

This update addresses three findings from the paper-to-system comparison. The research document is unchanged.

## Entitlement access

Only HR/staff can create, update, or delete leave allocations. Employees can list and retrieve their own allocations and balances. Allocation endpoints also require an active, onboarded account. Allocation years must fall between 1 and 9999, entitlements cannot be negative, and the existing employee/type/year uniqueness check returns a conflict for duplicates.

HR can manage entitlements in **Attendance > Leave Management > Annual leave allocations**. Choose the year and employee, then add an allocation or edit its number of days. Removing an override restores the configured default entitlement for that leave type; setting zero explicitly gives no entitlement. The editor shows allocated, used, and remaining days for the selected employee.

The employee **Leave Requests** panel includes **My leave balances**, with a year selector and refresh button. The balance API includes default leave types, explicitly allocated custom types, and types appearing in requests. It retains the existing calendar-day counting rule and can show a negative balance. This change does not introduce a new leave-accrual policy or automatically reject over-balance requests.

## Audit provenance

`EmployeeAuditLog.employee` continues to identify the affected employee. New `actor` and `actor_name` fields identify who performed an action and retain a display-name/username snapshot. Request-scoped middleware captures session and token-authenticated actors for explicit audit writes and model signals. Context is cleared after each request, including failures. Helpers which already receive an authenticated actor also pass that actor explicitly.

Old events retain an empty actor snapshot and display **Not recorded**. The update does not infer historical administrators from affected employees or action text. New events created without an authenticated actor are labeled **System**. The snapshot remains if the actor's account is later renamed or deleted.

The activity table separates **Performed by** and **Affected employee**. Actor-name and text filters run on the server before pagination. CSV export uses the same actor/text filters and includes separate actor identity and affected employee columns; category filtering is also applied during export. Employee audit access remains scoped to the affected employee, and HR-only Pay Estimate events remain inaccessible to employees.

## Activation and verification

Apply migration `0043_audit_actor` and any earlier pending migrations before starting the updated application. It adds nullable actor identity and a blank snapshot to existing audit rows. No application or production database was migrated during this update.

Five standalone tests passed for concurrent request isolation, nested context restoration, exception cleanup, authentication timing, and actor-label construction. These tests import neither Django nor external account services. Python AST checks, JavaScript syntax checks, and source/diff review also passed.

`tests/test_leave_allocation_access_and_audit.py` adds Django regressions for employee write denial and read scoping, HR CRUD, balance calculations, actor capture with session/token authentication, actor filtering, and historical snapshots. These tests have not been run: the previous automatic approval review stopped a Django attendance-security run because of unverified Visual Studio telemetry traffic. That blocked run was not retried. Browser automation was not used.

Changes are local and have not been pushed.
