from rest_framework import serializers
from .models import (
    Department, Employee, Attendance, LeaveRequest,
    ShiftRoster, PayrollRun, PayrollItem, PerformanceReview, ExpenseClaim, EmployeeAuditLog, Message, ClaimStatus
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

    # CUSTOM VALIDATOR: Prevents duplicate clock-ins on the same day
    def validate(self, data):
        if not self.instance and 'employee' in data and 'date' in data:
            if Attendance.objects.filter(employee=data['employee'], date=data['date']).exists():
                raise serializers.ValidationError("This employee has already clocked in today.")
        return data

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

class ExpenseClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseClaim
        fields = '__all__'

class EmployeeAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeAuditLog
        fields = '__all__'

class MessageSerializer(serializers.ModelSerializer):
    attachment = serializers.FileField(write_only=True, required=False, allow_null=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ('id', 'conversation_key', 'sender_name', 'text', 'attachment', 'attachment_url', 'created_at')
        read_only_fields = ('id', 'created_at', 'attachment_url')

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url

    def validate(self, attrs):
        if not attrs.get('text') and not self.context['request'].FILES.get('attachment'):
            raise serializers.ValidationError('A message or attachment is required.')
        return attrs

class ClaimStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimStatus
        fields = ('claim_id', 'status', 'updated_at')
        read_only_fields = ('updated_at',)
        extra_kwargs = {'claim_id': {'validators': []}}
