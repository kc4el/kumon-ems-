from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Employee, Attendance, LeaveRequest, EmployeeAuditLog

@receiver(post_save, sender=Employee)
def log_employee_creation(sender, instance, created, **kwargs):
    if created:
        EmployeeAuditLog.objects.create(
            employee=instance,
            action=f"Employee profile created for {instance.first_name} {instance.last_name}."
        )

@receiver(post_save, sender=Attendance)
def log_attendance_action(sender, instance, created, **kwargs):
    if created:
        EmployeeAuditLog.objects.create(
            employee=instance.employee,
            action=f"Clocked IN on {instance.date}."
        )
    elif instance.clock_out:
        EmployeeAuditLog.objects.create(
            employee=instance.employee,
            action=f"Clocked OUT on {instance.date}."
        )

@receiver(post_save, sender=LeaveRequest)
def log_leave_request(sender, instance, created, **kwargs):
    if created:
        EmployeeAuditLog.objects.create(
            employee=instance.employee,
            action=f"Submitted leave request (Status: {instance.status})."
        )
