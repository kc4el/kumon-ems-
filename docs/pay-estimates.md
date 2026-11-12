# Pay estimates

Pay Estimates are system-generated HR-only review aids. They are not employee
payslips, payroll finalization, or payment instructions. The person responsible
for actual pay must review the estimate, resolve incomplete inputs, apply any
relevant rules and deductions, and handle payment outside this workflow. Existing
legacy payroll runs and items remain preserved and their APIs are HR-only.

Each calculation records a revision and its input snapshot. Recalculation creates
an immutable historical revision rather than rewriting earlier calculation
results. Review decisions apply to the adjustments for the relevant revision.
Pending and rejected adjustments are excluded from the estimate total; only
approved adjustments contribute.

Base pay includes all worked hours used in the calculation. Overtime is an
incremental premium above base pay, not another full payment for those hours.
HR configures the daily overtime threshold and multiplier in an effective-dated
policy; without a configured policy, no overtime rate or threshold is assumed.
HR also configures which leave types are paid. An unset or empty list does not
assume that any leave type is paid. Approved adjustments still require review
against the applicable rules.

Scheduled breaks can be ambiguous when schedule and attendance information do
not clearly establish the break taken. Review warnings and completeness before
using an estimate; incomplete information must not be treated as verified pay.
Pending approvals are not included in the current total. Changes in source data
require a new calculation and review of its revision.

Estimates do not send employee notifications. Existing payroll-posted notices are
hidden from the employee inbox, while attendance-related overtime notices remain
available. The historical notification and legacy payroll records are retained.
Migration `0040` introduces the new estimate data; no production migration has
been performed as part of this work.

## Calculations and revisions

The period base is calculated from full-precision elapsed time and hourly rate,
then rounded to two decimal places. Daily amounts are also shown rounded to two
places. A separate rounding reconciliation explains any difference between the
sum of displayed daily amounts and the period base; it is not an approval item.

Same-effective-date policy corrections are published as new policy records.
Earlier records and calculation snapshots remain intact. Changes make affected
estimates outdated and require explicit recalculation. Incomplete data prevents
adjustment approval. Old revision approvals remain historical and cannot be
applied to a new revision. Estimate audit entries are HR-only.

Freshness checks are optimistic checks at read, export, and decision time;
attendance and policy writers are not globally locked by estimate review. A
subsequent source change makes the estimate outdated and suppresses its current
approved total. PostgreSQL concurrency behavior has not been verified here.

The existing authorized employee-retention purge can delete estimates together
with an employee, matching the lifecycle of the existing workforce records.
Normal estimate API operations do not delete revision history.

## Verification

The combined offline SQLite suite passed 31 tests: estimate engine and API,
legacy payroll access restrictions, notifications, and claim/case workflows.
JavaScript syntax and source/diff checks passed. The test runner disabled external
account SDK construction and Python socket connections for this run. Browser
automation was not performed, following the repository's testing preferences.

Run the focused verification with installed dependencies:

```text
python scripts/check_workflows_offline.py --no-external-services tests.test_pay_estimate_engine tests.test_pay_estimate_api tests.test_payroll_workflows tests.test_notification_workflows tests.test_case_workflows
```
