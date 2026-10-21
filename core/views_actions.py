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
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Attendance,
    AttendanceCorrection,
    Employee,
    EmployeeAuditLog,
    LeaveRequest,
    Notification,
    OvertimeSlip,
    ShiftRoster,
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

    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        if leave.status == "Approved":
            return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)

        leave.status = "Approved"
        leave.save(update_fields=["status"])

        EmployeeAuditLog.objects.create(
            employee=leave.employee,
            action=f"Leave request for {leave.leave_type} ({leave.start_date} to {leave.end_date}) was Approved by {request.user}.",
        )
        try:
            Notification.objects.create(
                employee=leave.employee,
                kind="leave",
                text=f"Your {leave.leave_type} leave request ({leave.start_date} to {leave.end_date}) has been Approved.",
            )
        except Exception:
            pass

        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)


class LeaveRejectView(APIView):
    """POST /api/leaves/<id>/reject/ - HR/Staff rejects a pending leave."""

    permission_classes = [IsStaffOrHR]

    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        reason = str(request.data.get("reason", "")).strip()

        if leave.status == "Rejected":
            return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)

        leave.status = "Rejected"
        leave.save(update_fields=["status"])

        log_msg = f"Leave request for {leave.leave_type} was Rejected by {request.user}."
        if reason:
            log_msg += f" Reason: {reason}"
        EmployeeAuditLog.objects.create(employee=leave.employee, action=log_msg)

        try:
            notif_msg = f"Your {leave.leave_type} leave request has been Rejected."
            if reason:
                notif_msg += f" Reason: {reason}"
            Notification.objects.create(
                employee=leave.employee,
                kind="leave",
                text=notif_msg,
            )
        except Exception:
            pass

        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_200_OK)


class LeaveBulkDecideView(APIView):
    """POST /api/leaves/bulk-decide/ - HR/Staff approves or rejects multiple leaves."""

    permission_classes = [IsStaffOrHR]

    def post(self, request):
        ids = request.data.get("ids", [])
        decision = request.data.get("decision", "").strip().capitalize()
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

        leaves = list(LeaveRequest.objects.filter(pk__in=ids))
        updated_count = 0
        with transaction.atomic():
            for leave in leaves:
                if leave.status != decision:
                    leave.status = decision
                    leave.save(update_fields=["status"])
                    updated_count += 1
                    EmployeeAuditLog.objects.create(
                        employee=leave.employee,
                        action=f"Bulk-decision: {leave.leave_type} leave {decision} by {request.user}.",
                    )
                    try:
                        Notification.objects.create(
                            employee=leave.employee,
                            kind="leave",
                            text=f"Your {leave.leave_type} leave request has been {decision} in batch.",
                        )
                    except Exception:
                        pass

        return Response(
            {"decision": decision, "updated_count": updated_count, "total_requested": len(ids)},
            status=status.HTTP_200_OK,
        )


class OvertimeSlipApproveView(APIView):
    """POST /api/overtime/<id>/approve/ - HR/Staff approves an overtime slip."""

    permission_classes = [IsStaffOrHR]

    def post(self, request, pk):
        slip = get_object_or_404(OvertimeSlip, pk=pk)
        slip.status = "Approved"
        slip.save(update_fields=["status"])

        EmployeeAuditLog.objects.create(
            employee=slip.employee,
            action=f"Overtime slip on {slip.date} ({slip.hours} hrs) Approved by {request.user}.",
        )
        try:
            Notification.objects.create(
                employee=slip.employee,
                kind="payroll",
                text=f"Your overtime slip for {slip.date} ({slip.hours} hrs) has been Approved.",
            )
        except Exception:
            pass

        return Response(OvertimeSlipSerializer(slip).data, status=status.HTTP_200_OK)


class OvertimeSlipRejectView(APIView):
    """POST /api/overtime/<id>/reject/ - HR/Staff rejects an overtime slip."""

    permission_classes = [IsStaffOrHR]

    def post(self, request, pk):
        slip = get_object_or_404(OvertimeSlip, pk=pk)
        reason = str(request.data.get("reason", "")).strip()

        slip.status = "Rejected"
        slip.save(update_fields=["status"])

        log_msg = f"Overtime slip on {slip.date} Rejected by {request.user}."
        if reason:
            log_msg += f" Reason: {reason}"
        EmployeeAuditLog.objects.create(employee=slip.employee, action=log_msg)

        try:
            Notification.objects.create(
                employee=slip.employee,
                kind="payroll",
                text=f"Your overtime slip for {slip.date} was Rejected.",
            )
        except Exception:
            pass

        return Response(OvertimeSlipSerializer(slip).data, status=status.HTTP_200_OK)


class AttendanceCorrectionApproveView(APIView):
    """POST /api/attendance-corrections/<id>/approve/ - HR/Staff approves correction and updates attendance times."""

    permission_classes = [IsStaffOrHR]

    def post(self, request, pk):
        correction = get_object_or_404(AttendanceCorrection, pk=pk)
        attendance = correction.attendance

        with transaction.atomic():
            correction.status = "Approved"
            correction.save(update_fields=["status"])

            updated_fields = []
            if correction.proposed_clock_in is not None:
                attendance.clock_in = correction.proposed_clock_in
                updated_fields.append("clock_in")
            if correction.proposed_clock_out is not None:
                attendance.clock_out = correction.proposed_clock_out
                updated_fields.append("clock_out")

            if updated_fields:
                attendance.save(update_fields=updated_fields)

            EmployeeAuditLog.objects.create(
                employee=attendance.employee,
                action=f"Attendance correction on {attendance.date} Approved by {request.user} ({', '.join(updated_fields)} adjusted).",
            )
            try:
                Notification.objects.create(
                    employee=attendance.employee,
                    kind="attendance",
                    text=f"Your attendance correction request for {attendance.date} has been Approved.",
                )
            except Exception:
                pass

        return Response(
            AttendanceCorrectionSerializer(correction).data, status=status.HTTP_200_OK
        )


class AttendanceCorrectionRejectView(APIView):
    """POST /api/attendance-corrections/<id>/reject/ - HR/Staff rejects attendance correction."""

    permission_classes = [IsStaffOrHR]

    def post(self, request, pk):
        correction = get_object_or_404(AttendanceCorrection, pk=pk)
        correction.status = "Rejected"
        correction.save(update_fields=["status"])

        EmployeeAuditLog.objects.create(
            employee=correction.attendance.employee,
            action=f"Attendance correction on {correction.attendance.date} Rejected by {request.user}.",
        )
        try:
            Notification.objects.create(
                employee=correction.attendance.employee,
                kind="attendance",
                text=f"Your attendance correction request for {correction.attendance.date} was Rejected.",
            )
        except Exception:
            pass

        return Response(
            AttendanceCorrectionSerializer(correction).data, status=status.HTTP_200_OK
        )


class ShiftSwapDecideView(APIView):
    """POST /api/shift-swaps/<id>/decide/ - Approves or rejects a shift swap and exchanges roster assignments."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        swap = get_object_or_404(ShiftSwap, pk=pk)
        decision = request.data.get("decision", "").strip().capitalize()
        if decision not in ("Approved", "Rejected"):
            return Response(
                {"error": 'decision must be "Approved" or "Rejected".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check authorization: user must be staff/HR or target roster's employee
        target_user = getattr(getattr(swap.target_roster, "employee", None), "user", None)
        if not is_staff_or_hr(request.user) and target_user != request.user:
            return Response(
                {"error": "Only the target shift employee or HR staff can decide this swap."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            swap.status = decision
            swap.save(update_fields=["status"])

            if decision == "Approved":
                # Swap employees on the two shift rosters
                emp_a = swap.requester_roster.employee
                emp_b = swap.target_roster.employee

                swap.requester_roster.employee = emp_b
                swap.target_roster.employee = emp_a
                swap.requester_roster.save(update_fields=["employee"])
                swap.target_roster.save(update_fields=["employee"])

                if emp_a:
                    EmployeeAuditLog.objects.create(
                        employee=emp_a,
                        action=f"Shift swap on {swap.requester_roster.work_date} Approved.",
                    )
                if emp_b:
                    EmployeeAuditLog.objects.create(
                        employee=emp_b,
                        action=f"Shift swap on {swap.target_roster.work_date} Approved.",
                    )

        return Response(ShiftSwapSerializer(swap).data, status=status.HTTP_200_OK)


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
