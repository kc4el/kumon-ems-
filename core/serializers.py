from django.db.models import Q
from rest_framework import serializers

from .exceptions import Conflict409
from .models import (
    Attendance,
    ClaimStatus,
    Department,
    Employee,
    EmployeeAuditLog,
    ExpenseClaim,
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
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


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
        return data


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LeaveAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveAllocation
        fields = ("id", "employee", "leave_type", "year", "days_total")
        read_only_fields = ("id",)


class OvertimeSlipSerializer(serializers.ModelSerializer):
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
        read_only_fields = ("id", "hours", "created_at")


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
