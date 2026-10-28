# Schema descriptions and normal forms by objective

These assessments use the declared keys in `schema.dbml` and business rules visible in the application. The labels reflect the highest normal form assessed from that information. Other business rules could change the assessment. PK means primary key; UK means non-null unique key.

## Objective 1: Performance and paid leave

| Table | Purpose | Normal form assessment |
|---|---|---|
| `core_employee` | Stores employee identity, role, department, and employment status. | **3NF.** `id` and `email` identify an employee. Department details are kept in a separate table. |
| `core_performancereview` | Stores an employee's review date, score, and comments. | **3NF.** Each review has its own `id`; review details describe that review. |
| `core_leaveallocation` | Stores leave days allocated to an employee for a leave type and year. | **3NF.** `id` identifies the row. `(employee_id, leave_type, year)` also uniquely identifies an allocation. `days_total` is assumed to depend on the whole combination. |
| `core_leaverequest` | Stores an employee's leave dates, type, reason, and status. | **3NF.** Each request has an `id`, and its details describe that request. |

## Objective 2: Time tracking and payroll

| Table | Purpose | Normal form assessment |
|---|---|---|
| `core_employee` | Identifies the employee whose time and pay are recorded. | **3NF.** Employee details are stored once and referenced by other tables. |
| `core_attendance` | Stores an employee's work date, clock-in, and clock-out. | **3NF.** Both `id` and `(employee_id, date)` identify an attendance row. Punch times are assumed to depend on the complete employee/date combination. |
| `core_attendancecorrection` | Stores proposed changes and their status for an attendance record. | **3NF.** Each correction has an `id`; attendance details remain in `core_attendance`. |
| `core_overtimeslip` | Stores overtime hours, multiplier, status, employee, and attendance reference. | **3NF.** Both `id` and unique `attendance_id` identify a slip. Employee and date are also stored here, so they must stay consistent with attendance; this duplication alone does not establish a 3NF violation. |
| `core_payrollrun` | Stores a pay period and whether it has been processed. | **3NF.** The run's `id` identifies its period and status. |
| `core_payrollitem` | Stores an employee's base pay, deductions, and net pay for a payroll run. | **2NF.** `id` and `(payroll_run_id, employee_id)` identify the row. The application calculates `net_pay` from `base_pay` and `deductions`, so non-key values determine another non-key value. That dependency prevents 3NF if the calculation is required for all rows. The schema itself does not enforce the formula. |

## Objective 3: Shift scheduling and notifications

| Table | Purpose | Normal form assessment |
|---|---|---|
| `core_employee` | Identifies employees assigned to shifts or receiving notifications. | **3NF.** Employee information is separate from shift and notification records. |
| `core_shiftroster` | Stores a shift's employee, date, type, times, and break. | **3NF.** `id` identifies the shift. The schema does not say that `shift_type` determines the times; if that is a business rule, this assessment needs review. |
| `core_shiftswap` | Stores a swap request between two roster entries, its reason, and status. | **3NF.** Each swap has an `id` and references roster entries rather than repeating their details. |
| `core_notification` | Stores a notification, its recipient, type, read state, and creation time. | **3NF.** Each notification has an `id`; its contents and read state describe that notification. |

## Objective 4: Role access and two-factor authentication

| Table | Purpose | Normal form assessment |
|---|---|---|
| `auth_user` | Stores login account details and account flags. | **3NF.** `id` and `username` identify an account. The schema declares no other determinant for the account attributes. |
| `auth.user_groups` | Assigns users to groups. | **3NF.** Both `id` and `(user_id, group_id)` identify an assignment. The row contains the assignment pair and its identifier. |
| `auth_group` | Stores group names used to organize permissions. | **3NF.** Both `id` and `name` identify a group. |
| `auth.group_permissions` | Assigns permissions to groups. | **3NF.** Both `id` and `(group_id, permission_id)` identify an assignment. |
| `auth_permission` | Stores permission names and codenames for a content type. | **3NF.** Both `id` and `(content_type_id, codename)` identify a permission. The name is assumed to depend on the whole pair. |
| `core_authenticatordevice` | Stores an account's encrypted authenticator secret and verification state. | **3NF.** Both `id` and unique `user_id` identify the device. |
| `core_authenticatorrecoverycode` | Stores hashed recovery credentials for an authenticator. | **3NF.** Each recovery code has its own `id`; device details remain in the device table. |

## Objective 5: Cloud database and integrity

These tables also support the other objectives. Cloud hosting does not change their normal forms.

| Table | Purpose | Normal form assessment |
|---|---|---|
| `core_department` | Stores department name, code, manager, and timestamps. | **3NF.** `id` and `name` identify a department. `code` is unique but nullable, so it is not treated as a candidate key for all rows. |
| `core_employee` | Stores the central employee record. | **3NF.** `id` and `email` identify an employee; department details are separate. |
| `core_attendance` | Stores daily attendance records. | **3NF.** `id` and `(employee_id, date)` identify each record. |
| `core_payrollrun` | Groups payroll records by pay period. | **3NF.** The run's `id` identifies its period and processing state. |
| `core_payrollitem` | Stores one employee's pay values within a run. | **2NF**, because stored net pay is calculated from other non-key values. |

These labels describe the current design. A formal 3NF proof needs confirmation of all candidate keys and business dependencies. See [the detailed table assessment](normalization-table-assessment.md) for the declared keys and assumptions.
