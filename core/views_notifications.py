"""Private notification inbox endpoints."""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (AttendanceCorrection, Complaint, ExpenseClaim, Grievance, LeaveRequest,
                     Notification, OvertimeSlip, ShiftRoster, ShiftSwap, UserSetting)


class InboxNotificationSerializer(serializers.ModelSerializer):
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "employee", "text", "kind", "is_read", "created_at",
                  "target_type", "target_id", "target_url")
        read_only_fields = fields

    def get_target_url(self, obj):
        if obj.target_id and obj.target_type == "shift_swap":
            if ShiftSwap.objects.filter(Q(requester_employee_id=obj.employee_id) | Q(target_employee_id=obj.employee_id), pk=obj.target_id).exists():
                return f"/api/shift-swaps/{obj.target_id}/"
            return None
        if obj.target_id and obj.target_type == "attendance_correction":
            if AttendanceCorrection.objects.filter(pk=obj.target_id, attendance__employee_id=obj.employee_id).exists():
                return f"/api/attendance-corrections/{obj.target_id}/"
            return None
        targets = {
            "leave": ("leaves", LeaveRequest), "shift": ("shift-rosters", ShiftRoster),
            "claim": ("expense-claims", ExpenseClaim), "complaint": ("complaints", Complaint),
            "grievance": ("grievances", Grievance),
            "overtime": ("overtime", OvertimeSlip),
        }
        target = targets.get(obj.target_type)
        if not target or not obj.target_id:
            return None
        path, model = target
        if not model.objects.filter(pk=obj.target_id, employee_id=obj.employee_id).exists():
            return None
        return f"/api/{path}/{obj.target_id}/"


def owned_notifications(user):
    return Notification.objects.filter(employee__user=user, employee__is_active=True).exclude(
        Q(target_type__in=["payroll", "payroll_item"]) |
        Q(kind="payroll", text__istartswith="Payroll posted")
    )


class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InboxNotificationSerializer

    def get_queryset(self):
        qs = owned_notifications(self.request.user).order_by("-created_at")
        setting = UserSetting.objects.filter(user=self.request.user).first()
        muted = setting.muted_kinds if setting else []
        if isinstance(muted, list):
            qs = qs.exclude(kind__in=[kind for kind in muted if isinstance(kind, str)])
        return qs


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        note = get_object_or_404(owned_notifications(request.user), pk=pk)
        if not note.is_read:
            note.is_read = True
            note.save(update_fields=["is_read"])
        return Response(InboxNotificationSerializer(note).data)
