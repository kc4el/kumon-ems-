import logging
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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
from .serializers import (
    AttendanceSerializer,
    DepartmentSerializer,
    EmployeeAuditLogSerializer,
    EmployeeSerializer,
    LeaveRequestSerializer,
    PayrollItemSerializer,
    PayrollRunSerializer,
    PerformanceReviewSerializer,
    ShiftRosterSerializer,
)
from .supabase_client import supabase

logger = logging.getLogger(__name__)


def dashboard_view(request):
    return render(request, "core/index.html")


def login_view(request):
    return render(request, "core/login.html")


class DashboardSummaryView(APIView):
    """Return the aggregate counts required by the dashboard landing page."""

    # Public aggregate counts for the landing page (intentional; see B10)
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            total_employees = Employee.objects.count()
            active_employees = Employee.objects.filter(is_active=True).count()
            approved_leaves = LeaveRequest.objects.filter(
                status__iexact="approved"
            ).count()
            pending_leaves = LeaveRequest.objects.filter(
                status__iexact="pending"
            ).count()
            open_attendance = Attendance.objects.filter(clock_out__isnull=True).count()

            return Response(
                {
                    "total_employees": total_employees,
                    "active_employees": active_employees,
                    "approved_leaves": approved_leaves,
                    "pending_leaves": pending_leaves,
                    "open_attendance_records": open_attendance,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Dashboard summary error: {e}")
            return Response(
                {"error": "Unable to load dashboard summary."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DepartmentListCreateView(generics.ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    pagination_class = None


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class EmployeeListCreateView(generics.ListCreateAPIView):
    queryset = Employee.objects.all().order_by("id")
    serializer_class = EmployeeSerializer

    def post(self, request, *args, **kwargs):
        payload = request.data.copy()
        email = str(payload.get("email", "")).strip()
        if not email:
            return Response(
                {"error": "An employee email address is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=payload)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            return Response({"error": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        if Employee.objects.filter(email__iexact=email).exists():
            return Response(
                {"error": "An employee with this email already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        created_user_id = None
        try:
            record_id = str(uuid.uuid4())
            auth_response = supabase.auth.admin.create_user(
                {
                    "id": record_id,
                    "email": email,
                    "email_confirm": True,
                    "user_metadata": {
                        "first_name": payload.get("first_name", ""),
                        "last_name": payload.get("last_name", ""),
                    },
                }
            )
            created_user_id = str(auth_response.user.id)
            serializer.save(id=created_user_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as error:
            if created_user_id:
                try:
                    supabase.auth.admin.delete_user(created_user_id)
                except Exception:
                    logger.exception(
                        f"Unable to roll back Supabase Auth user {created_user_id}"
                    )
            logger.warning(f"Unable to create employee: {error}")
            return Response(
                {"error": "Unable to create employee upstream. Try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer


class AttendanceListCreateView(generics.ListCreateAPIView):
    queryset = Attendance.objects.all().order_by("-date", "-clock_in")
    serializer_class = AttendanceSerializer

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise Conflict409("This employee has already clocked in on this date.")


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer


class AttendanceClockOutView(APIView):
    def post(self, request):
        emp_id = request.data.get("employee_id")
        if not emp_id:
            return Response(
                {"error": "employee_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw_out = request.data.get("clock_out")
        if raw_out:
            clock_out_time = parse_datetime(str(raw_out))
            if clock_out_time is None:
                return Response(
                    {"error": "clock_out must be an ISO-8601 datetime."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if timezone.is_naive(clock_out_time):
                clock_out_time = timezone.make_aware(clock_out_time)
        else:
            clock_out_time = timezone.now()
        try:
            with transaction.atomic():
                open_rows = (
                    Attendance.objects.select_for_update()
                    .filter(employee_id=emp_id, clock_out__isnull=True)
                    .order_by("clock_in")
                )
                count = open_rows.count()
                if count == 0:
                    return Response(
                        {"error": "No open clock-in found for this employee."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                if count > 1:
                    return Response(
                        {"error": "Multiple open clock-ins; resolve manually."},
                        status=status.HTTP_409_CONFLICT,
                    )
                attendance = open_rows.first()
                if attendance.clock_in and clock_out_time < attendance.clock_in:
                    return Response(
                        {"error": "clock_out cannot precede clock_in."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                attendance.clock_out = clock_out_time
                attendance.save()
                return Response(
                    {"message": "Clocked out successfully."},
                    status=status.HTTP_200_OK,
                )
        except (DjangoValidationError, ValueError):
            return Response(
                {"error": "Invalid employee_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LeaveRequestListCreateView(generics.ListCreateAPIView):
    queryset = LeaveRequest.objects.all().order_by("-created_at")
    serializer_class = LeaveRequestSerializer


class LeaveRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer


class ShiftRosterListCreateView(generics.ListCreateAPIView):
    queryset = ShiftRoster.objects.all().order_by("id")
    serializer_class = ShiftRosterSerializer


class ShiftRosterDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftRoster.objects.all()
    serializer_class = ShiftRosterSerializer


class PayrollRunListCreateView(generics.ListCreateAPIView):
    queryset = PayrollRun.objects.all().order_by("id")
    serializer_class = PayrollRunSerializer


class PayrollRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollRun.objects.all()
    serializer_class = PayrollRunSerializer


class PayrollItemListCreateView(generics.ListCreateAPIView):
    queryset = PayrollItem.objects.all().order_by("id")
    serializer_class = PayrollItemSerializer


class PayrollItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer


class PerformanceReviewListCreateView(generics.ListCreateAPIView):
    queryset = PerformanceReview.objects.all().order_by("id")
    serializer_class = PerformanceReviewSerializer


class PerformanceReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer


class EmployeeAuditLogListView(generics.ListAPIView):
    queryset = EmployeeAuditLog.objects.all().order_by("-timestamp")
    serializer_class = EmployeeAuditLogSerializer
