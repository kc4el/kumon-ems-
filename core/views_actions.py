"""Workflow action endpoints and employee self-service backends.

Provides dedicated endpoints for:
- Leave request approve, reject, and bulk-decide
- Overtime slip approve and reject
- Attendance correction approve (with clock adjustment) and reject
- Shift swap accept/approve and reject
- Shift roster bulk creation
- Employee self-service profile and payout/bank details
"""

import logging
import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AttendanceCorrection,
    Employee,
    EmployeeAuditLog,
    LeaveRequest,
    Notification,
    OvertimeSlip,
    ShiftSwap,
    UserSetting,
)
from .permissions import IsStaffOrHR, is_staff_or_hr
from .serializers import (
    AttendanceCorrectionSerializer,
    EmployeeSerializer,
    LeaveRequestSerializer,
    OvertimeSlipSerializer,
    ShiftRosterSerializer,
    ShiftSwapSerializer,
)

logger = logging.getLogger(__name__)


class LeaveApproveView(APIView):
    """POST /api/leaves/<id>/approve/ - HR/Staff approves a pending leave."""

    permission_classes = [IsStaffOrHR]

    @transaction.atomic
    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest.objects.select_for_update(), pk=pk)
        if leave.status == "Approved":
            return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)
        if leave.status != "Pending":
            return Response({"error": "This request has already been decided."}, status=status.HTTP_409_CONFLICT)

        leave.status = "Approved"
        leave.save(update_fields=["status"])

        EmployeeAuditLog.objects.create(
            employee=leave.employee,
            action=f"Leave request for {leave.leave_type} ({leave.start_date} to {leave.end_date}) was Approved by {request.user}.",
        )

        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)


class LeaveRejectView(APIView):
    """POST /api/leaves/<id>/reject/ - HR/Staff rejects a pending leave."""

    permission_classes = [IsStaffOrHR]

    @transaction.atomic
    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest.objects.select_for_update(), pk=pk)
        reason = str(request.data.get("reason", "")).strip()

        if leave.status == "Rejected":
            return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)
        if leave.status != "Pending":
            return Response({"error": "This request has already been decided."}, status=status.HTTP_409_CONFLICT)

        leave.status = "Rejected"
        leave.save(update_fields=["status"])

        log_msg = f"Leave request for {leave.leave_type} was Rejected by {request.user}."
        if reason:
            log_msg += f" Reason: {reason}"
        EmployeeAuditLog.objects.create(employee=leave.employee, action=log_msg)


        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)


class LeaveBulkDecideView(APIView):
    """POST /api/leaves/bulk-decide/ - HR/Staff approves or rejects multiple leaves."""

    permission_classes = [IsStaffOrHR]

    def post(self, request):
        ids = request.data.get("ids", [])
        decision = request.data.get("decision", "")
        if not isinstance(decision, str):
            return Response({"error": "decision must be a string."}, status=status.HTTP_400_BAD_REQUEST)
        decision = decision.strip().capitalize()
        reason = str(request.data.get("reason", "")).strip()

        if decision not in ("Approved", "Rejected"):
            return Response(
                {"error": 'decision must be "Approved" or "Rejected".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": "ids must be a non-empty list of leave request IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ids = [uuid.UUID(str(value)) for value in ids]
        except (ValueError, TypeError, AttributeError):
            return Response({"error": "Each id must be a valid UUID."}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        with transaction.atomic():
            leaves = list(LeaveRequest.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            if len(leaves) != len(set(ids)):
                return Response({"error": "One or more leave requests were not found."}, status=status.HTTP_400_BAD_REQUEST)
            if any(leave.status not in ("Pending", decision) for leave in leaves):
                return Response({"error": "This request has already been decided."}, status=status.HTTP_409_CONFLICT)
            for leave in leaves:
                if leave.status == "Pending":
                    leave.status = decision
                    leave.save(update_fields=["status"])
                    updated_count += 1
                    EmployeeAuditLog.objects.create(
                        employee=leave.employee,
                        action=f"Bulk-decision: {leave.leave_type} leave {decision} by {request.user}.",
                    )

        return Response(
            {"decision": decision, "updated_count": updated_count, "total_requested": len(ids)},
            status=status.HTTP_200_OK,
        )


class OvertimeSlipApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .views_staff_requests import decide_overtime
        return Response(OvertimeSlipSerializer(decide_overtime(pk, "Approved", request.user)).data)


class OvertimeSlipRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .views_staff_requests import decide_overtime
        return Response(OvertimeSlipSerializer(decide_overtime(pk, "Rejected", request.user)).data)


class AttendanceCorrectionApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .views_staff_requests import decide_correction
        return Response(AttendanceCorrectionSerializer(decide_correction(pk, "Approved", request.user)).data)


class AttendanceCorrectionRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .views_staff_requests import decide_correction
        return Response(AttendanceCorrectionSerializer(decide_correction(pk, "Rejected", request.user)).data)


class ShiftSwapDecideView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .views_staff_requests import decide_swap
        decision = str(request.data.get("decision", "")).strip().capitalize()
        return Response(ShiftSwapSerializer(decide_swap(pk, decision, request.user)).data)


class ShiftRosterBulkCreateView(APIView):
    """POST /api/shift-rosters/bulk/ - HR/Staff bulk generates/publishes shift assignments."""

    permission_classes = [IsStaffOrHR]

    def post(self, request):
        shifts = request.data.get("shifts", [])
        if not isinstance(shifts, list) or not shifts:
            return Response(
                {"error": "shifts must be a non-empty list of roster objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_records = []
        errors = []
        with transaction.atomic():
            for index, item in enumerate(shifts):
                ser = ShiftRosterSerializer(data=item)
                if ser.is_valid():
                    ser.save()
                    created_records.append(ser.data)
                else:
                    errors.append({"index": index, "errors": ser.errors})

            if errors:
                transaction.set_rollback(True)
                return Response(
                    {"error": "Validation failed for some shift records.", "details": errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {"created_count": len(created_records), "shifts": created_records},
            status=status.HTTP_201_CREATED,
        )


class EmployeeMeView(APIView):
    """GET /api/employees/me/ - Fetch current authenticated employee profile.
    PATCH /api/employees/me/ - Self-service profile updates (phone, emergency contacts).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = Employee.objects.filter(user=request.user).first()
        if not employee:
            return Response(
                {"error": "No employee profile linked to current account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = EmployeeSerializer(employee).data
        # Include custom contact info stored in UserSetting
        setting, _ = UserSetting.objects.get_or_create(user=request.user)
        contact_info = setting.dashboard_widgets.get("contact_info", {})
        data["contact_info"] = contact_info
        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request):
        employee = Employee.objects.filter(user=request.user).first()
        if not employee:
            return Response(
                {"error": "No employee profile linked to current account."},
                status=status.HTTP_404_NOT_FOUND,
            )

        setting, _ = UserSetting.objects.get_or_create(user=request.user)
        contact_info = setting.dashboard_widgets.get("contact_info", {})

        allowed_fields = ("phone_number", "home_address", "emergency_contact_name", "emergency_contact_phone")
        for field in allowed_fields:
            if field in request.data:
                contact_info[field] = str(request.data[field]).strip()

        widgets = dict(setting.dashboard_widgets)
        widgets["contact_info"] = contact_info
        setting.dashboard_widgets = widgets
        setting.save(update_fields=["dashboard_widgets"])

        data = EmployeeSerializer(employee).data
        data["contact_info"] = contact_info
        return Response(data, status=status.HTTP_200_OK)


class EmployeePayoutView(APIView):
    """GET /api/employees/me/payout/ - View direct deposit & bank details.
    POST / PATCH /api/employees/me/payout/ - Update direct deposit & bank details.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        setting, _ = UserSetting.objects.get_or_create(user=request.user)
        payout = setting.dashboard_widgets.get("payout_details", {
            "bank_name": "",
            "account_number": "",
            "account_holder": "",
            "tin_number": "",
            "sss_number": "",
            "philhealth_number": "",
            "pagibig_number": "",
        })
        # Mask account number for security (e.g. ****1234)
        masked_payout = dict(payout)
        raw_acct = masked_payout.get("account_number", "")
        if len(raw_acct) > 4:
            masked_payout["account_number_masked"] = "*" * (len(raw_acct) - 4) + raw_acct[-4:]
        else:
            masked_payout["account_number_masked"] = raw_acct
        return Response(masked_payout, status=status.HTTP_200_OK)

    def post(self, request):
        return self.patch(request)

    def patch(self, request):
        setting, _ = UserSetting.objects.get_or_create(user=request.user)
        payout = dict(setting.dashboard_widgets.get("payout_details", {}))

        fields = (
            "bank_name",
            "account_number",
            "account_holder",
            "tin_number",
            "sss_number",
            "philhealth_number",
            "pagibig_number",
        )
        for field in fields:
            if field in request.data:
                payout[field] = str(request.data[field]).strip()

        widgets = dict(setting.dashboard_widgets)
        widgets["payout_details"] = payout
        setting.dashboard_widgets = widgets
        setting.save(update_fields=["dashboard_widgets"])

        return Response(
            {"message": "Payout details updated successfully.", "payout": payout},
            status=status.HTTP_200_OK,
        )


from django.urls import path

action_urls = [
    path("leaves/<uuid:pk>/approve/", LeaveApproveView.as_view(), name="leave-approve"),
    path("leaves/<uuid:pk>/reject/", LeaveRejectView.as_view(), name="leave-reject"),
    path("leaves/bulk-decide/", LeaveBulkDecideView.as_view(), name="leave-bulk-decide"),
    path("overtime/<uuid:pk>/approve/", OvertimeSlipApproveView.as_view(), name="overtime-approve"),
    path("overtime/<uuid:pk>/reject/", OvertimeSlipRejectView.as_view(), name="overtime-reject"),
    path("attendance-corrections/<uuid:pk>/approve/", AttendanceCorrectionApproveView.as_view(), name="attendance-correction-approve"),
    path("attendance-corrections/<uuid:pk>/reject/", AttendanceCorrectionRejectView.as_view(), name="attendance-correction-reject"),
    path("shift-swaps/<uuid:pk>/decide/", ShiftSwapDecideView.as_view(), name="shift-swap-decide"),
    path("shift-rosters/bulk/", ShiftRosterBulkCreateView.as_view(), name="shift-roster-bulk"),
    path("employees/me/", EmployeeMeView.as_view(), name="employee-me"),
    path("employees/me/payout/", EmployeePayoutView.as_view(), name="employee-me-payout"),
]
