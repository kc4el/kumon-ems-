# Kumon EMS ERD

[Download the transparent 1920×1080 PNG](erd.png) · [Download the A4 landscape PDF](../output/pdf/kumon-ems-erd-a4.pdf)

![Rendered entity relationship diagram](erd.png)

White table cards with black text list every field and its PostgreSQL type. `PK` and `FK` tags mark key columns, `?` marks nullable fields, and each FK tag includes its connector ID. All 30 tables appear once. The canvas is transparent.

Relationship endpoints use full cardinality marks: an open circle means zero (optional), a bar means one, and a fork means many. Orthogonal connector paths route around table cards. Connector IDs match this guide and are checked against the foreign-key nullability and uniqueness in `schema.dbml`. Cardinality is written as “parent rows per child; child rows per parent.”

| ID | Connection | Cardinality | Why they are linked / what the connection supports |
|---|---|---|---|
| R01 | auth_group.id → auth.group_permissions.group_id | 1 parent per child; 0..* children per parent | stores group grants so members inherit these permissions |
| R02 | auth_permission.id → auth.group_permissions.permission_id | 1 parent per child; 0..* children per parent | records this permission in a group's shared access rules |
| R03 | auth_user.id → auth.user_groups.user_id | 1 parent per child; 0..* children per parent | records which access groups grant roles to this login |
| R04 | auth_group.id → auth.user_groups.group_id | 1 parent per child; 0..* children per parent | links users to groups whose permissions they inherit |
| R05 | auth_user.id → auth.user_user_permissions.user_id | 1 parent per child; 0..* children per parent | stores access exceptions granted directly to this account |
| R06 | auth_permission.id → auth.user_user_permissions.permission_id | 1 parent per child; 0..* children per parent | defines the action granted directly to this login account |
| R07 | django_content_type.id → auth_permission.content_type_id | 1 parent per child; 0..* children per parent | scopes permissions to an app and model for Django access checks |
| R08 | core_employee.id → core_attendance.employee_id | 1 parent per child; 0..* children per parent | ties clock records to staff for timesheets and attendance history |
| R09 | core_attendance.id → core_attendancecorrection.attendance_id | 1 parent per child; 0..* children per parent | anchors each correction request to the punch record it asks to fix |
| R10 | core_employee.id → core_complaint.employee_id | 1 parent per child; 0..* children per parent | identifies the complainant so cases can be tracked by owner |
| R11 | core_employee.id → core_department.manager_id | 0..1 parent per child; 0..* children per parent | identifies the department manager for oversight and approval routing; optional |
| R12 | core_department.id → core_employee.department_id | 0..1 parent per child; 0..* children per parent | assigns staff to an org unit for filtering and reporting; optional |
| R13 | auth_user.id → core_employee.user_id | 0..1 parent per child; 0..1 children per parent | maps login sessions to a staff profile for portal ownership and access; one to one, optional |
| R14 | core_employee.id → core_employeeauditlog.employee_id | 0..1 parent per child; 0..* children per parent | attributes actions to staff for accountability; actor link may be empty |
| R15 | core_employee.id → core_expenseclaim.employee_id | 1 parent per child; 0..* children per parent | identifies the claimant so reimbursement can be reviewed and paid |
| R16 | core_employee.id → core_grievance.employee_id | 0..1 parent per child; 0..* children per parent | links case history to staff when known; association is optional |
| R17 | core_employee.id → core_leaveallocation.employee_id | 1 parent per child; 0..* children per parent | stores annual balances for leave eligibility checks |
| R18 | core_employee.id → core_leaverequest.employee_id | 1 parent per child; 0..* children per parent | identifies requester so leave can be approved and scoped to its owner |
| R19 | core_employee.id → core_notification.employee_id | 1 parent per child; 0..* children per parent | targets in-app messages and tracks read status for each staff member |
| R20 | core_employee.id → core_onboardingdocument.employee_id | 1 parent per child; 0..* children per parent | files required paperwork under the employee onboarding record |
| R21 | core_employee.id → core_overtimeslip.employee_id | 1 parent per child; 0..* children per parent | identifies the overtime claimant for approval and compensation |
| R22 | core_attendance.id → core_overtimeslip.attendance_id | 1 parent per child; 0..1 children per parent | ties claimed extra hours to attendance evidence; at most one slip per record |
| R23 | core_payrollrun.id → core_payrollitem.payroll_run_id | 1 parent per child; 0..* children per parent | groups staff pay lines into a pay period for processing |
| R24 | core_employee.id → core_payrollitem.employee_id | 1 parent per child; 0..* children per parent | assigns each pay line to the person receiving the wages |
| R25 | core_employee.id → core_performancereview.employee_id | 1 parent per child; 0..* children per parent | keeps scores and comments in the staff review history |
| R26 | core_employee.id → core_salaryadvance.employee_id | 1 parent per child; 0..* children per parent | tracks the borrower and repayment under the staff advance record |
| R27 | core_employee.id → core_shiftroster.employee_id | 0..1 parent per child; 0..* children per parent | assigns planned shifts to staff; empty employee allows an unfilled slot |
| R28 | core_shiftroster.id → core_shiftswap.requester_roster_id | 1 parent per child; 0..* children per parent | marks the roster entry whose holder requested the exchange |
| R29 | core_shiftroster.id → core_shiftswap.target_roster_id | 1 parent per child; 0..* children per parent | marks the roster entry requested as the exchange target |
| R30 | auth_user.id → core_authenticatordevice.user_id | 1 parent per child; 0..1 children per parent | attaches MFA settings to the login account protected by TOTP; one device max |
| R31 | core_authenticatordevice.id → core_authenticatorrecoverycode.device_id | 1 parent per child; 0..* children per parent | stores backup codes with their authenticator; each code is single use |

Full column definitions and indexes are in [schema.dbml](schema.dbml).

## What each table is for

- `auth.group_permissions`: This table has group and permission assignments and is used for granting shared permissions to groups.
- `auth.user_groups`: This table has user-to-group assignments and is used for giving users the permissions attached to their groups.
- `auth.user_user_permissions`: This table has direct user-to-permission assignments and is used for granting account-specific permissions.
- `auth_group`: This table has named access groups and is used for grouping users under shared permissions.
- `auth_permission`: This table has permission names, actions, and model links and is used for Django authorization checks.
- `auth_user`: This table has login credentials, profile fields, and account flags and is used for authentication and account access.
- `core_attendance`: This table has an employee, work date, and clock-in and clock-out times and is used for daily attendance records.
- `core_attendancecorrection`: This table has an attendance link, proposed times, reason, and status and is used for requesting punch corrections.
- `core_authenticatordevice`: This table has a user link, encrypted authenticator secret, and verification state and is used for two-factor login.
- `core_authenticatorrecoverycode`: This table has an authenticator-device link and hashed recovery codes and is used for single-use account recovery.
- `core_claimstatus`: This table has a claim ID, current status, and update time and is used for tracking each claim's status.
- `core_complaint`: This table has an employee, complaint details, category, and status and is used for recording and resolving complaints.
- `core_department`: This table has a department name, code, and optional manager and is used for organizing staff and routing oversight.
- `core_employee`: This table has staff profile, job, department, and optional login details and is used as the central employee record.
- `core_employeeauditlog`: This table has an employee link, action, and timestamp and is used for recording employee-related activity.
- `core_expenseclaim`: This table has an employee, expense details, amount, and status and is used for submitting and reviewing reimbursements.
- `core_grievance`: This table has optional employee details, a case category, description, and status and is used for tracking grievances.
- `core_leaveallocation`: This table has an employee, leave type, year, and available days and is used for tracking annual leave balances.
- `core_leaverequest`: This table has an employee, leave dates, reason, and status and is used for requesting and approving leave.
- `core_message`: This table has a conversation key, sender, message text, and optional attachment and is used for storing announcements and messages.
- `core_notification`: This table has an employee, notification text, kind, and read state and is used for delivering in-app notifications.
- `core_onboardingdocument`: This table has an employee, document type, file, and upload time and is used for storing onboarding paperwork.
- `core_overtimeslip`: This table has an employee, attendance record, hours, multiplier, and status and is used for reviewing and paying overtime.
- `core_payrollitem`: This table has a payroll run, employee, base pay, deductions, and net pay and is used for each employee's payroll line.
- `core_payrollrun`: This table has a pay-period start, end, and processed flag and is used for grouping payroll items into a payroll batch.
- `core_performancereview`: This table has an employee, review date, score, and comments and is used for maintaining performance review history.
- `core_salaryadvance`: This table has an employee, amount, repayment terms, purpose, and status and is used for managing salary advance requests.
- `core_shiftroster`: This table has shift dates, times, type, and an optional employee and is used for scheduling assigned or open shifts.
- `core_shiftswap`: This table has requester and target shifts, a reason, and status and is used for managing shift exchange requests.
- `django_content_type`: This table has application and model names and is used for identifying models referenced by Django permissions.
