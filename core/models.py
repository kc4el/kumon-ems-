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
    requester_employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="requested_shift_swaps",
    )
    target_employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="targeted_shift_swaps",
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


class PayEstimate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="pay_estimates")
    period_start = models.DateField()
    period_end = models.DateField()
    hourly_rate = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    current_revision = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_pay_estimates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="estimate_valid_period"),
            models.CheckConstraint(condition=models.Q(hourly_rate__gte=0), name="estimate_rate_nonnegative"),
            models.CheckConstraint(condition=models.Q(deductions__gte=0), name="estimate_deductions_nonnegative"),
        ]


class PayEstimatePolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    effective_date = models.DateField(db_index=True)
    overtime_threshold_hours = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    overtime_multiplier = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    paid_leave_types = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_pay_estimate_policies")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("effective_date", "created_at", "id")
        constraints = [
            models.CheckConstraint(condition=(models.Q(overtime_threshold_hours__isnull=True, overtime_multiplier__isnull=True) | models.Q(overtime_threshold_hours__isnull=False, overtime_multiplier__isnull=False, overtime_threshold_hours__gte=0, overtime_multiplier__gte=1)), name="estimate_policy_valid_overtime"),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.paid_leave_types, list) or any(not isinstance(v, str) or not v.strip() for v in self.paid_leave_types):
            raise ValidationError({"paid_leave_types": "Provide a list of nonempty leave type names."})
        if (self.overtime_threshold_hours is None) != (self.overtime_multiplier is None):
            raise ValidationError("Overtime threshold and multiplier must both be supplied or both omitted.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Estimate policies are immutable; create a new effective-dated policy.")
        super().save(*args, **kwargs)


class PayEstimateRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    estimate = models.ForeignKey(PayEstimate, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    input_snapshot = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    base_amount = models.DecimalField(max_digits=14, decimal_places=2)
    deductions = models.DecimalField(max_digits=12, decimal_places=2)
    is_complete = models.BooleanField(default=True)
    warnings = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("estimate", "number"), name="unique_estimate_revision")]
        ordering = ("-number",)


class PayEstimateLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(PayEstimateRevision, on_delete=models.CASCADE, related_name="lines")
    work_date = models.DateField()
    attendance = models.ForeignKey(Attendance, null=True, blank=True, on_delete=models.SET_NULL)
    worked_seconds = models.DecimalField(max_digits=16, decimal_places=6)
    break_seconds = models.DecimalField(max_digits=16, decimal_places=6)
    paid_seconds = models.DecimalField(max_digits=16, decimal_places=6)
    base_amount = models.DecimalField(max_digits=14, decimal_places=2)
    source = models.JSONField(default=dict)


class PayEstimateAdjustment(models.Model):
    class Kind(models.TextChoices):
        OVERTIME = "OVERTIME", "Overtime"
        PAID_LEAVE = "PAID_LEAVE", "Paid leave"

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(PayEstimateRevision, on_delete=models.CASCADE, related_name="adjustments")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    work_date = models.DateField()
    hours = models.DecimalField(max_digits=16, decimal_places=6)
    hourly_rate = models.DecimalField(max_digits=12, decimal_places=2)
    multiplier = models.DecimalField(max_digits=8, decimal_places=4)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_pay_estimate_adjustments")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    source_key = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("revision", "source_key"), name="unique_estimate_adjustment_source"),
            models.CheckConstraint(condition=models.Q(status__in=["Pending", "Approved", "Rejected"]), name="estimate_adjustment_valid_status"),
            models.CheckConstraint(condition=models.Q(kind__in=["OVERTIME", "PAID_LEAVE"]), name="estimate_adjustment_valid_kind"),
        ]


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
    resolution = models.TextField(blank=True, default="")
    internal_notes = models.TextField(blank=True, default="")
    source_complaint = models.OneToOneField(
        "Complaint", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="escalated_grievance",
    )
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
    resolution = models.TextField(blank=True, default="")
    internal_notes = models.TextField(blank=True, default="")
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
    target_type = models.CharField(max_length=30, blank=True, default="")
    target_id = models.UUIDField(null=True, blank=True)
    event_key = models.CharField(max_length=160, null=True, blank=True, unique=True)
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
