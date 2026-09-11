import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (
    Attendance,
    Department,
    Employee,
    EmployeeAuditLog,
    LeaveRequest,
    Notification,
    PayrollItem,
    PayrollRun,
    PerformanceReview,
    ShiftRoster,
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
    previous_status = getattr(instance, "_previous_status", None)
    if created or (previous_status and previous_status != instance.status):
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
