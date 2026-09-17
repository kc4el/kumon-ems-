import logging
from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from .exceptions import Conflict409
from .models import (
    Attendance,
    AttendanceCorrection,
    ClaimStatus,
    Complaint,
    Department,
    Employee,
    EmployeeAuditLog,
    ExpenseClaim,
    Grievance,
    LeaveAllocation,
    LeaveRequest,
    Message,
    Notification,
    OvertimeSlip,
    PayrollItem,
    PayrollRun,
    PerformanceReview,
    ShiftRoster,
    ShiftSwap,
    SiteSetting,
    UserSetting,
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class GrievanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_department = serializers.SerializerMethodField()
    employee_role = serializers.SerializerMethodField()

    class Meta:
        model = Grievance
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "employee_name",
            "employee_department",
            "employee_role",
        )

    def get_employee_name(self, obj):
        return str(obj.employee) if obj.employee else "Anonymous Filing"

    def get_employee_department(self, obj):
        return (
            obj.employee.department.name
            if obj.employee and obj.employee.department
            else ""
        )

    def get_employee_role(self, obj):
        return obj.employee.role if obj.employee and obj.employee.role else ""


class ComplaintSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = "__all__"
        read_only_fields = ("id", "created_at", "employee_name")
        extra_kwargs = {"employee": {"required": False}}

    def get_employee_name(self, obj):
        return str(obj.employee)


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "role",
            "department",
            "date_hired",
            "is_active",
        ]
        read_only_fields = ["id", "date_hired"]


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = "__all__"
        # No auto unique-together validator: the fast-path Conflict409 below
        # plus the DB constraint are the single enforcement path (409 rule).
        validators = []

    # CUSTOM VALIDATOR: Prevents duplicate clock-ins on the same day
    def validate(self, data):
        if not self.instance and "employee" in data and "date" in data:
            if Attendance.objects.filter(
                employee=data["employee"], date=data["date"]
            ).exists():
                raise Conflict409("This employee has already clocked in today.")

        # Clock order: direct writes must not invert the pair either.
        def val(name):
            if name in data:
                return data[name]
            return getattr(self.instance, name, None) if self.instance else None

        start, end = val("clock_in"), val("clock_out")
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError("clock_out must be after clock_in.")
        return data


class AttendanceCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceCorrection
        fields = (
            "id",
            "attendance",
            "proposed_clock_in",
            "proposed_clock_out",
            "reason",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, data):
        def val(name):
            if name in data:
                return data[name]
            return getattr(self.instance, name, None) if self.instance else None

        proposed_in = val("proposed_clock_in")
        proposed_out = val("proposed_clock_out")
        if not self.instance and proposed_in is None and proposed_out is None:
            raise serializers.ValidationError("At least one proposed time is required.")
        attendance = val("attendance")
        start = (
            proposed_in
            if proposed_in is not None
            else getattr(attendance, "clock_in", None)
        )
        end = (
            proposed_out
            if proposed_out is not None
            else getattr(attendance, "clock_out", None)
        )
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError(
                "proposed_clock_out must be after proposed_clock_in."
            )
        return data


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_department = serializers.SerializerMethodField()
    employee_role = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_department",
            "employee_role",
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"employee": {"required": False}}

    def get_employee_name(self, obj):
        return str(obj.employee)

    def get_employee_department(self, obj):
        return obj.employee.department.name if obj.employee.department else ""

    def get_employee_role(self, obj):
        return obj.employee.role or ""

    def validate_leave_type(self, value):
        return value.strip().title()

    def validate(self, data):
        data = super().validate(data)

        def val(name):
            if name in data:
                return data[name]
            return getattr(self.instance, name, None) if self.instance else None

        start, end = val("start_date"), val("end_date")
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError("end_date must not precede start_date.")
        return data


class LeaveAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveAllocation
        fields = ("id", "employee", "leave_type", "year", "days_total")
        read_only_fields = ("id",)
        # No auto unique-together validator: duplicate allocation is a 409
        # conflict (raised by the view), not a malformed request.
        validators = []

    def validate_leave_type(self, value):
        return value.strip().title()


class OvertimeSlipSerializer(serializers.ModelSerializer):
    STATUS_CHOICES = ("Pending", "Approved", "Rejected")
    status = serializers.ChoiceField(choices=STATUS_CHOICES, default="Pending")
    hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    # Multiplier bounds are NOT hardcoded here: they follow the
    # overtime_min_hours / overtime_max_hours SiteSettings (see validate),
    # defaulting to 0.01/5.00 when unset or invalid.
    multiplier = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.25"),
        required=False,
    )

    class Meta:
        model = OvertimeSlip
        fields = (
            "id",
            "employee",
            "attendance",
            "date",
            "hours",
            "multiplier",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, data):
        data = super().validate(data)

        def val(name):
            if name in data:
                return data[name]
            return getattr(self.instance, name, None) if self.instance else None

        if self.instance is not None:
            for field in ("employee", "attendance", "hours"):
                if field in data and data[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {field: "This field cannot be changed."}
                    )

        attendance = val("attendance")
        slip_date = val("date")
        employee = val("employee")
        if attendance is not None and slip_date is not None:
            if slip_date != attendance.date:
                raise serializers.ValidationError(
                    {"date": "Date must match the attendance date."}
                )
        if attendance is not None and employee is not None:
            if employee.id != attendance.employee_id:
                raise serializers.ValidationError(
                    {"attendance": "Attendance does not belong to this employee."}
                )
        multiplier = val("multiplier")
        if multiplier is not None:
            # Bounds are the overtime_min/max_hours SiteSettings (source of
            # truth), defaulting to 0.01/5.00 when unset or invalid.
            lo = _site_decimal("overtime_min_hours", Decimal("0.01"))
            hi = _site_decimal("overtime_max_hours", Decimal("5.00"))
            if lo > hi:
                lo, hi = Decimal("0.01"), Decimal("5.00")
            if not (lo <= Decimal(str(multiplier)) <= hi):
                raise serializers.ValidationError(
                    {
                        "multiplier": (
                            "Must be between "
                            f"{lo} and {hi} (overtime_min/max_hours)."
                        )
                    }
                )
        return data


class ShiftRosterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftRoster
        fields = "__all__"

    def validate(self, data):
        def val(name):
            return data.get(name, getattr(self.instance, name, None))

        employee, day, start, end = (
            val("employee"),
            val("work_date"),
            val("start_time"),
            val("end_time"),
        )
        if employee and day and start and end:
            if start >= end:
                raise serializers.ValidationError("start_time must be before end_time.")
            clash = ShiftRoster.objects.filter(
                employee=employee,
                work_date=day,
                start_time__lt=end,
                end_time__gt=start,
            )
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise Conflict409("Shift overlaps an existing assignment.")
        return data


class ShiftSwapSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftSwap
        fields = (
            "id",
            "requester_roster",
            "target_roster",
            "reason",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, data):
        def val(name):
            return data.get(name, getattr(self.instance, name, None))

        requester = val("requester_roster")
        target = val("target_roster")
        if requester and target:
            if requester.pk == target.pk:
                raise serializers.ValidationError("Cannot swap a roster with itself.")
            if requester.employee_id == target.employee_id:
                raise serializers.ValidationError(
                    "Swaps must be between different employees."
                )
            if requester.work_date != target.work_date:
                raise serializers.ValidationError("Swaps must be for the same date.")
            pending = ShiftSwap.objects.filter(status="Pending").filter(
                Q(requester_roster__in=[requester.pk, target.pk])
                | Q(target_roster__in=[requester.pk, target.pk])
            )
            if self.instance:
                pending = pending.exclude(pk=self.instance.pk)
            if pending.exists():
                raise Conflict409("A swap is already pending for this roster.")
        return data


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = "__all__"

    def validate(self, data):
        def val(name):
            if name in data:
                return data[name]
            return getattr(self.instance, name, None) if self.instance else None

        start, end = val("pay_period_start"), val("pay_period_end")
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError(
                "pay_period_end must not precede pay_period_start."
            )
        return data


class PayrollItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollItem
        fields = ["id", "payroll_run", "employee", "base_pay", "deductions", "net_pay"]
        read_only_fields = ["id", "net_pay"]
        # No auto unique-together validator: the DB is the single enforcer and
        # IntegrityError maps to 409 (unified conflict rule), race included.
        validators = []


class PerformanceReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceReview
        fields = "__all__"


class ExpenseClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseClaim
        fields = (
            "id",
            "employee",
            "title",
            "amount",
            "category",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class EmployeeAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAuditLog
        fields = "__all__"


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "employee", "text", "kind", "is_read", "created_at")
        read_only_fields = ("id", "created_at")


class MessageSerializer(serializers.ModelSerializer):
    attachment = serializers.FileField(write_only=True, required=False, allow_null=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation_key",
            "sender_name",
            "text",
            "attachment",
            "attachment_url",
            "created_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "attachment_url",
            "sender_name",
            "conversation_key",
        )

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get("request")
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url

    def validate(self, attrs):
        if not attrs.get("text") and not self.context["request"].FILES.get(
            "attachment"
        ):
            raise serializers.ValidationError("A message or attachment is required.")
        return attrs


class ClaimStatusSerializer(serializers.ModelSerializer):
    STATUS_CHOICES = ("Pending", "Approved", "Rejected")
    status = serializers.ChoiceField(choices=STATUS_CHOICES)

    class Meta:
        model = ClaimStatus
        fields = ("claim_id", "status", "updated_at")
        read_only_fields = ("updated_at",)
        extra_kwargs = {
            "claim_id": {
                "validators": [],
                "allow_blank": False,
                "trim_whitespace": True,
            }
        }


SITE_SETTING_SPECS = {
    "overtime_min_hours": {"min": 0, "max": 24},
    "overtime_max_hours": {"min": 0, "max": 24},
    "purge_retention_days": {"min": 1, "max": 365, "integer": True},
    "onboarding_max_mb": {"min": 1, "max": 100, "integer": True},
    "leave_restrict_backdated": {"bool": True},
    "leave_auto_allocate_days": {"min": 0, "max": 365, "integer": True},
    "shift_allow_double_booking": {"bool": True},
    "payroll_round_net": {"bool": True},
    "mobile_checkin_enabled": {"bool": True},
}

# Local SiteSetting reader (kept here instead of importing get_site_setting
# from .views: views.py imports this module, so that import would be circular).
# Falls back to SITE_SETTING_DEFAULTS when unset, invalid, or on DB error.
SITE_SETTING_DEFAULTS = {
    "overtime_min_hours": "0.01",
    "overtime_max_hours": "5.00",
    "purge_retention_days": "30",
    "onboarding_max_mb": "10",
    "leave_restrict_backdated": "false",
    "leave_auto_allocate_days": "0",
    "shift_allow_double_booking": "false",
    "payroll_round_net": "false",
    "mobile_checkin_enabled": "true",
}


def _site_val(key):
    default = SITE_SETTING_DEFAULTS.get(key, "")
    try:
        val = (
            SiteSetting.objects.filter(key=key).values_list("value", flat=True).first()
            or default
        )
        if val != default:
            float(val)  # corrupt stored values fall through to default + log
        return val
    except Exception:
        logger = logging.getLogger(__name__)
        logger.warning(
            "SiteSetting %s unreadable/invalid, using default %s", key, default
        )
        return default


def _site_decimal(key, fallback):
    try:
        return Decimal(str(_site_val(key)))
    except Exception:
        logger = logging.getLogger(__name__)
        logger.warning(
            "SiteSetting %s invalid decimal, using fallback %s", key, fallback
        )
        return fallback


MUTABLE_PROFILE_FIELDS = ("first_name", "last_name", "email")


class UserSettingSerializer(serializers.ModelSerializer):
    page_size = serializers.IntegerField(min_value=5, max_value=100)
    muted_kinds = serializers.ListField(
        child=serializers.ChoiceField(choices=["leave", "shift", "payroll"]),
        required=False,
    )
    dashboard_widgets = serializers.DictField(required=False)
    a11y = serializers.DictField(required=False)

    class Meta:
        model = UserSetting
        fields = ("page_size", "muted_kinds", "dashboard_widgets", "a11y")

    def validate_a11y(self, value):
        allowed_scales = [87.5, 100, 112.5, 125]
        if "font_scale" in value and value["font_scale"] not in allowed_scales:
            raise serializers.ValidationError(
                f"font_scale must be one of {allowed_scales}."
            )
        for flag in ("high_contrast", "reduce_motion"):
            if flag in value and not isinstance(value[flag], bool):
                raise serializers.ValidationError(f"{flag} must be true/false.")
        unknown = set(value) - {"font_scale", "high_contrast", "reduce_motion"}
        if unknown:
            raise serializers.ValidationError(f"Unknown a11y keys: {sorted(unknown)}.")
        return value


class SiteSettingSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=list(SITE_SETTING_SPECS))
    value = serializers.CharField(max_length=200)

    def validate(self, attrs):
        spec = SITE_SETTING_SPECS[attrs["key"]]
        if spec.get("bool"):
            if str(attrs["value"]).lower() not in ("true", "false"):
                raise serializers.ValidationError('value must be "true" or "false".')
            return attrs
        try:
            num = float(attrs["value"])
        except (TypeError, ValueError):
            raise serializers.ValidationError("value must be numeric.")
        if spec.get("integer") and not num.is_integer():
            raise serializers.ValidationError("value must be a whole number.")
        if not (spec["min"] <= num <= spec["max"]):
            raise serializers.ValidationError(
                f"value must be between {spec['min']} and {spec['max']}."
            )
        return attrs
