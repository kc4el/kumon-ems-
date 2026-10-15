# Database normalization notes

This note records the account-security schema added in migration `0030_authenticatordevice`, the supporting document type in `0031_onboardingdocument_government_records`, and the model/schema alignment in `0032_remove_attendance_one_open_attendance_per_employee_per_day_and_more`.

## Two-factor authentication

- `AuthenticatorDevice` has one row per Django user and stores the encrypted TOTP secret, enablement state, and last accepted counter. The one-to-one user key prevents multiple active authenticators per account.
- `AuthenticatorRecoveryCode` has one row per recovery code. It stores only a password-hashed code and points to its authenticator device. Using a recovery code deletes that row, so the remaining credentials are naturally countable and individually consumable.
- Recovery codes are not stored as a JSON array on the device. A repeating group is represented as related rows, preserving first normal form and keeping device state separate from each credential.
- Deleting a device cascades to its recovery rows. The migration is additive and has no existing application rows to rewrite.

## Existing flexible preferences

`UserSetting` keeps notification kinds, dashboard widgets, and accessibility preferences in JSON fields because these are small user-owned preference documents, not independently identified business entities. Attendance, leave, payroll, and organization records remain relational and use explicit foreign keys.

## Existing date and attendance constraints

Migration `0032` adds the model-declared date indexes for attendance, leave requests, and shift rosters. It removes a redundant conditional attendance constraint; the existing `(employee, date)` unique constraint remains and continues to prevent duplicate daily attendance rows.

## ERD files

- `schema.dbml` is the editable relational source and includes the new account-security relationships.
- `chapter3/figures/figure2-erd.html` adds the account-security detail diagram below the existing business ERD.

Biometric and NFC attendance tables are intentionally not included while that feature remains undecided.
