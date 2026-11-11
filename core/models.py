import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .constants import NUMERIC_RANGES


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
    class OnboardingStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PENDING_ONBOARDING = "PENDING_ONBOARDING", "Pending onboarding"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee_id = models.CharField(max_length=16, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    # ADDED: Frontend relies on displaying the employee's role/job title
    role = models.CharField(max_length=100, blank=True, null=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_hired = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=24,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.ACTIVE,
    )
    force_password_change = models.BooleanField(default=False)
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


class AccountCredential(models.Model):
    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name="account_credential"
    )
    password_hash = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)


class OAuthLink(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"

    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name="oauth_link"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    subject = models.CharField(max_length=255)
    email = models.EmailField()
    email_verified = models.BooleanField(default=False)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "subject"),
                name="unique_oauth_provider_subject",
            )
        ]


class Attendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField(db_index=True)
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("employee", "date"),
                name="unique_attendance_employee_date",
            )
        ]


class AttendanceQrSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        USED = "USED", "Used"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=128, unique=True, db_index=True)
    manual_code = models.CharField(max_length=6, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE and timezone.now() < self.expires_at

    def invalidate(self, *, used=False):
        now = timezone.now()
        self.invalidated_at = now
        self.used_at = now if used else self.used_at
        self.status = self.Status.USED if used else self.Status.EXPIRED
        self.save(update_fields=["used_at", "invalidated_at", "status"])


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
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
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
    work_date = models.DateField(null=True, blank=True, db_index=True)
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
    base_pay = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    deductions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal("0"))],
    )
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
    updated_at = models.DateTimeField(auto_now=True)


class EmployeeAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


class Grievance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True
    )
    category = models.CharField(max_length=150)
    title = models.CharField(max_length=255)
    details = models.TextField()
    status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Investigating", "Investigating"),
            ("In Mediation", "In Mediation"),
            ("Resolved", "Resolved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)


class Complaint(models.Model):
    class Status(models.TextChoices):
        OPEN = "Open", "Open"
        IN_REVIEW = "In Review", "In Review"
        RESOLVED = "Resolved", "Resolved"
        DISMISSED = "Dismissed", "Dismissed"

    class Category(models.TextChoices):
        WORKPLACE = "workplace", "Workplace conduct"
        HARASSMENT = "harassment", "Harassment"
        PAYROLL = "payroll", "Payroll issue"
        GENERAL = "general", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="complaints"
    )
    subject = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.GENERAL
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    is_confidential = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.subject} ({self.employee_id})"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_key = models.CharField(max_length=100, default="announcements", db_index=True)
    sender_name = models.CharField(max_length=255, default="System")
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


class UserSetting(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="setting"
    )
    page_size = models.PositiveSmallIntegerField(default=10)
    muted_kinds = models.JSONField(default=list)
    dashboard_widgets = models.JSONField(default=dict)
    a11y = models.JSONField(default=dict)

    def __str__(self):
        return f"settings({self.user_id})"


class AuthenticatorDevice(models.Model):
    """One encrypted TOTP authenticator per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="authenticator_device",
    )
    encrypted_secret = models.CharField(max_length=512)
    is_confirmed = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)
    last_verified_counter = models.BigIntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"authenticator({self.user_id})"


class AuthenticatorRecoveryCode(models.Model):
    """A single hashed, one-use recovery code for an authenticator device."""

    device = models.ForeignKey(
        AuthenticatorDevice,
        on_delete=models.CASCADE,
        related_name="recovery_codes",
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)


class SiteSetting(models.Model):
    key = models.CharField(max_length=80, unique=True)
    value = models.CharField(max_length=200)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.key in NUMERIC_RANGES:
            try:
                num = float(self.value)
            except (TypeError, ValueError):
                raise ValidationError(f"{self.key} must be numeric.")
            lo, hi = NUMERIC_RANGES[self.key]
            if not (lo <= num <= hi):
                raise ValidationError(f"{self.key} must be between {lo} and {hi}.")

    def __str__(self):
        return f"{self.key}={self.value}"
