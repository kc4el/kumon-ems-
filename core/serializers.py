from rest_framework import serializers

from .exceptions import Conflict409
from .models import (
    Attendance,
    Department,
    Employee,
    EmployeeAuditLog,
    LeaveRequest,
    PayrollItem,
    PayrollRun,
    PerformanceReview,
    ShiftRoster,
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


class EmployeeAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAuditLog
        fields = "__all__"
