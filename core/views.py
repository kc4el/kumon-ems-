import logging
import uuid
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
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
    ClaimStatus,
    Department,
    Employee,
    EmployeeAuditLog,
    ExpenseClaim,
    LeaveRequest,
    Message,
    PayrollItem,
    PayrollRun,
    PerformanceReview,
    ShiftRoster,
)
from .serializers import (
    AttendanceSerializer,
    ClaimStatusSerializer,
    DepartmentSerializer,
    EmployeeAuditLogSerializer,
    EmployeeSerializer,
    ExpenseClaimSerializer,
    LeaveRequestSerializer,
    MessageSerializer,
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
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class EmployeeListCreateView(generics.ListCreateAPIView):
    queryset = Employee.objects.all().order_by("last_name", "first_name")
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
            with transaction.atomic():
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
        except IntegrityError:
            logger.warning(f"Duplicate employee race for {email}")
            return Response(
                {"error": "An employee with this email already exists."},
                status=status.HTTP_409_CONFLICT,
            )
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

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.resigned_at = timezone.now().date()
        instance.save(update_fields=["is_active", "resigned_at"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_active:
            instance.is_active = False
            instance.resigned_at = timezone.now().date()
            instance.save(update_fields=["is_active", "resigned_at"])
        purge_on = (
            instance.resigned_at + timedelta(days=30) if instance.resigned_at else None
        )
        if not EmployeeAuditLog.objects.filter(
            employee=instance, action__icontains="resigned"
        ).exists():
            EmployeeAuditLog.objects.create(
                employee=instance,
                action=f"resigned {instance.resigned_at}, purge on {purge_on}",
            )
        return Response(
            {
                "id": str(instance.id),
                "is_active": False,
                "resigned_at": instance.resigned_at,
                "purge_on": purge_on,
            },
            status=status.HTTP_200_OK,
        )


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

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise Conflict409("This change conflicts with an existing record.")


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
    queryset = ShiftRoster.objects.all().order_by("work_date", "start_time")
    serializer_class = ShiftRosterSerializer


class ShiftRosterDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftRoster.objects.all()
    serializer_class = ShiftRosterSerializer


class PayrollRunListCreateView(generics.ListCreateAPIView):
    queryset = PayrollRun.objects.all().order_by("-pay_period_start")
    serializer_class = PayrollRunSerializer


class PayrollRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollRun.objects.all()
    serializer_class = PayrollRunSerializer


class PayrollItemListCreateView(generics.ListCreateAPIView):
    queryset = PayrollItem.objects.all().order_by(
        "payroll_run__pay_period_start", "employee__last_name"
    )
    serializer_class = PayrollItemSerializer

    def perform_create(self, serializer):
        self._save_computed(serializer)

    @staticmethod
    def _save_computed(serializer):
        base = serializer.validated_data.get(
            "base_pay", getattr(serializer.instance, "base_pay", None)
        )
        deductions = serializer.validated_data.get(
            "deductions", getattr(serializer.instance, "deductions", 0)
        )
        if base is None:
            raise DRFValidationError({"base_pay": "This field is required."})
        try:
            with transaction.atomic():
                serializer.save(net_pay=base - deductions)
        except IntegrityError:
            raise Conflict409("Duplicate payroll line for this run and employee.")


class PayrollItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer

    def perform_update(self, serializer):
        PayrollItemListCreateView._save_computed(serializer)


class PerformanceReviewListCreateView(generics.ListCreateAPIView):
    queryset = PerformanceReview.objects.all().order_by("-review_date")
    serializer_class = PerformanceReviewSerializer


class PerformanceReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer


class EmployeeAuditLogListView(generics.ListAPIView):
    queryset = EmployeeAuditLog.objects.all().order_by("-timestamp")
    serializer_class = EmployeeAuditLogSerializer


class SessionLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = authenticate(
            request,
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
        if user is None:
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response({"message": "Signed in."}, status=status.HTTP_200_OK)


class SessionLogoutView(APIView):
    def post(self, request):
        if request.auth:
            request.auth.delete()
        logout(request)
        return Response({"message": "Signed out."}, status=status.HTTP_200_OK)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation_key = self.request.query_params.get("conversation", "sarah")
        return Message.objects.filter(conversation_key=conversation_key)

    def perform_create(self, serializer):
        serializer.save(
            conversation_key=self.request.data.get("conversation_key", "sarah"),
            sender_name=self.request.data.get("sender_name", "Marcus Williams"),
        )


class ClaimStatusListCreateView(generics.ListCreateAPIView):
    queryset = ClaimStatus.objects.all().order_by("claim_id")
    serializer_class = ClaimStatusSerializer

    def perform_create(self, serializer):
        claim_id = self.request.data.get("claim_id")
        status_value = self.request.data.get("status")
        serializer.instance, _ = ClaimStatus.objects.update_or_create(
            claim_id=claim_id,
            defaults={"status": status_value},
        )


class ExpenseClaimListCreateView(generics.ListCreateAPIView):
    queryset = ExpenseClaim.objects.all().order_by("-created_at")
    serializer_class = ExpenseClaimSerializer


class ExpenseClaimDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ExpenseClaim.objects.all()
    serializer_class = ExpenseClaimSerializer
