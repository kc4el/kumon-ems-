import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (
    Attendance,
    AttendanceCorrection,
    Department,
    Employee,
    EmployeeAuditLog,
    LeaveAllocation,
    LeaveRequest,
    Notification,
    OvertimeSlip,
    PayrollItem,
    PayrollRun,
    PerformanceReview,
    ShiftRoster,
    ShiftSwap,
)

logger = logging.getLogger(__name__)


def create_audit_log(employee, action):
    EmployeeAuditLog.objects.create(employee=employee, action=action)
    logger.info("Audit: %s -> %s", employee, action)


@receiver(pre_save, sender=Attendance)
def cache_attendance_state(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_clock_out = (
            Attendance.objects.filter(pk=instance.pk)
            .values_list("clock_out", flat=True)
            .first()
        )


@receiver(pre_save, sender=LeaveRequest)
def cache_leave_state(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_status = (
            LeaveRequest.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=Employee)
def log_employee_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance,
            f"Employee profile created for {instance.first_name} {instance.last_name}.",
        )
    else:
        # Soft-delete (EmployeeDetailView.destroy) writes its own distinct
        # "resigned ..." row; skip the generic update log for that save so
        # exactly one audit row results.
        if set(kwargs.get("update_fields") or []) == {"is_active", "resigned_at"}:
            return
        create_audit_log(
            instance,
            f"Employee profile updated for {instance.first_name} {instance.last_name}.",
        )


@receiver(post_save, sender=Department)
def log_department_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.manager,
            f"Department {instance.name} created.",
        )
    else:
        create_audit_log(
            instance.manager,
            f"Department {instance.name} updated.",
        )


@receiver(post_save, sender=Attendance)
def log_attendance_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(instance.employee, f"Clocked IN on {instance.date}.")
        return

    previous_clock_out = getattr(instance, "_previous_clock_out", None)
    if instance.clock_out and not previous_clock_out:
        create_audit_log(instance.employee, f"Clocked OUT on {instance.date}.")


@receiver(post_save, sender=LeaveRequest)
def log_leave_request(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.employee,
            f"Submitted leave request (Status: {instance.status}).",
        )
        return

    previous_status = getattr(instance, "_previous_status", None)
    if previous_status and previous_status != instance.status:
        create_audit_log(
            instance.employee,
            f"Leave request status changed from {previous_status} to {instance.status}.",
        )


@receiver(post_save, sender=ShiftRoster)
def log_shift_roster_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.employee if hasattr(instance, "employee") else None,
            f"Shift roster created for {instance.name or 'schedule'}.",
        )
    else:
        create_audit_log(
            instance.employee if hasattr(instance, "employee") else None,
            f"Shift roster updated for {instance.name or 'schedule'}.",
        )


@receiver(post_save, sender=PayrollRun)
def log_payroll_run_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            None,
            f"Payroll run created for {instance.pay_period_start} to {instance.pay_period_end}.",
        )
    else:
        create_audit_log(
            None,
            f"Payroll run updated for {instance.pay_period_start} to {instance.pay_period_end}.",
        )


@receiver(post_save, sender=PayrollItem)
def log_payroll_item_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.employee, f"Payroll item created for {instance.employee}."
        )
        Notification.objects.create(
            employee=instance.employee,
            text=f"Payroll posted: net {instance.net_pay} for {instance.payroll_run}",
            kind="payroll",
        )
    else:
        create_audit_log(
            instance.employee, f"Payroll item updated for {instance.employee}."
        )


@receiver(post_save, sender=PerformanceReview)
def log_performance_review_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.employee, f"Performance review created for {instance.employee}."
        )
    else:
        create_audit_log(
            instance.employee, f"Performance review updated for {instance.employee}."
        )


@receiver(post_save, sender=LeaveRequest)
def notify_leave_decision(sender, instance, created, **kwargs):
    # Submit (Pending) stays silent. Decision only.
    if created:
        return
    previous_status = getattr(instance, "_previous_status", None)
    if not (previous_status and previous_status != instance.status):
        return
    if instance.status == "Pending":
        return
    text = f"Leave {instance.status}: {instance.start_date}–{instance.end_date}"
    if instance.status == "Approved":
        from .views import leave_balance

        balance = leave_balance(
            instance.employee_id, instance.leave_type, instance.start_date.year
        )
        if balance["remaining"] < 0:
            text += f" ({balance['remaining']} days over balance)"
    Notification.objects.create(
        employee=instance.employee,
        text=text,
        kind="leave",
    )


@receiver(post_save, sender=ShiftRoster)
def notify_shift_assignment(sender, instance, created, **kwargs):
    if created and instance.employee_id:
        Notification.objects.create(
            employee_id=instance.employee_id,
            text=f"You were assigned {instance.shift_type} on {instance.work_date}",
            kind="shift",
        )


@receiver(pre_save, sender=OvertimeSlip)
def cache_overtime_status(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_status = (
            OvertimeSlip.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=OvertimeSlip)
def notify_overtime_approval(sender, instance, created, **kwargs):
    if instance.status != "Approved":
        return
    if not created and getattr(instance, "_previous_status", None) == "Approved":
        return
    Notification.objects.create(
        employee=instance.employee,
        text=f"Overtime approved: {instance.hours}h × {instance.multiplier} on {instance.date}",
        kind="payroll",
    )


@receiver(post_save, sender=LeaveAllocation)
def log_allocation_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.employee,
            f"Leave allocation set: {instance.days_total} {instance.leave_type} days for {instance.year}.",
        )


@receiver(post_save, sender=OvertimeSlip)
def log_overtime_action(sender, instance, created, **kwargs):
    if created:
        create_audit_log(
            instance.employee,
            f"Overtime requested: {instance.hours}h on {instance.date}.",
        )
    elif getattr(instance, "_previous_status", None) not in (None, instance.status):
        create_audit_log(
            instance.employee,
            f"Overtime {instance.status.lower()}: {instance.hours}h on {instance.date}.",
        )


@receiver(pre_save, sender=ShiftSwap)
def cache_swap_status(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_status = (
            ShiftSwap.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=ShiftSwap)
def log_swap_action(sender, instance, created, **kwargs):
    parties = {
        e
        for e in (
            getattr(instance.requester_roster, "employee", None),
            getattr(instance.target_roster, "employee", None),
        )
        if e is not None
    }
    if created:
        create_audit_log(
            instance.requester_roster.employee,
            f"Shift swap requested for {instance.requester_roster.work_date}.",
        )
        # Both parties learn a swap exists. Silent request = missed shift.
        for emp in parties:
            Notification.objects.create(
                employee=emp,
                text=f"Shift swap requested for {instance.requester_roster.work_date}",
                kind="shift",
            )
    elif getattr(instance, "_previous_status", None) not in (None, instance.status):
        create_audit_log(
            instance.requester_roster.employee,
            f"Shift swap {instance.status.lower()} for {instance.requester_roster.work_date}.",
        )
        for emp in parties:
            Notification.objects.create(
                employee=emp,
                text=(
                    f"Shift swap {instance.status.lower()} "
                    f"for {instance.requester_roster.work_date}"
                ),
                kind="shift",
            )
