from rest_framework import serializers
from .models import (
    Department, Employee, Attendance, LeaveRequest, 
    ShiftRoster, PayrollRun, PayrollItem, PerformanceReview, EmployeeAuditLog
)

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'

class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'

class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = '__all__'

class ShiftRosterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftRoster
        fields = '__all__'

class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = '__all__'

class PayrollItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollItem
        fields = '__all__'

class PerformanceReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceReview
        fields = '__all__'

class EmployeeAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAuditLog
        fields = '__all__'