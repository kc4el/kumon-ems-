import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    manager = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    # ADDED: Frontend relies on displaying the employee's role/job title
    role = models.CharField(max_length=100, blank=True, null=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_hired = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    resigned_at = models.DateField(null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Attendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)

    # ADDED: Enforce at the Database level that an employee can only have 1 record per day
    class Meta:
        unique_together = ("employee", "date")
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"],
                condition=Q(clock_out__isnull=True),
                name="one_open_attendance_per_employee_per_day",
            )
        ]


class OvertimeSlip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    attendance = models.OneToOneField(Attendance, on_delete=models.CASCADE)
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("1.25")
    )
    status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.attendance_id and self.employee_id:
            if self.attendance.employee_id != self.employee_id:
                raise ValidationError(
                    {
                        "attendance": "Overtime slip employee must match attendance employee."
                    }
                )


class AttendanceCorrection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    proposed_clock_in = models.DateTimeField(null=True, blank=True)
    proposed_clock_out = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class LeaveRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=50, default="Personal")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)


LEAVE_DEFAULTS = {"Vacation": 5, "Sick": 5}


class LeaveAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=50)
    year = models.IntegerField()
    days_total = models.DecimalField(
        max_digits=5, decimal_places=1, validators=[MinValueValidator(Decimal("0"))]
    )

    class Meta:
        unique_together = ("employee", "leave_type", "year")
        ordering = ("-year", "leave_type")


class ShiftRoster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True
    )
    work_date = models.DateField(null=True, blank=True)
    shift_type = models.CharField(max_length=50, default="General")
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_mins = models.IntegerField(default=0)
    # FIX: Added auto_now_add and auto_now so Django handles these automatically
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ShiftSwap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester_roster = models.ForeignKey(
        ShiftRoster, on_delete=models.CASCADE, related_name="swap_requests"
    )
    target_roster = models.ForeignKey(
        ShiftRoster, on_delete=models.CASCADE, related_name="swap_targets"
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PayrollRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pay_period_start = models.DateField()
    pay_period_end = models.DateField()
    is_processed = models.BooleanField(default=False)


class PayrollItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    base_pay = models.DecimalField(max_digits=10, decimal_places=2)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ("payroll_run", "employee")


class PerformanceReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    review_date = models.DateField()
    score = models.IntegerField()
    comments = models.TextField()


class ExpenseClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    category = models.CharField(max_length=100, default="General Expense")
    status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )  # Pending, Approved, Rejected
    created_at = models.DateTimeField(auto_now_add=True)


class EmployeeAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_key = models.CharField(max_length=100, default="sarah", db_index=True)
    sender_name = models.CharField(max_length=255, default="Marcus Williams")
    text = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="message-attachments/%Y/%m/%d/", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class ClaimStatus(models.Model):
    claim_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    kind = models.CharField(max_length=50, default="info")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
