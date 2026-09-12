import logging
import uuid
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, models, transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import Conflict409
from .models import (
    Attendance,
    AttendanceCorrection,
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
from .permissions import IsOwnerOrStaff, OwnerQuerysetMixin
from .serializers import (
    AttendanceCorrectionSerializer,
    AttendanceSerializer,
    ClaimStatusSerializer,
    DepartmentSerializer,
    EmployeeAuditLogSerializer,
    EmployeeSerializer,
    ExpenseClaimSerializer,
    LeaveAllocationSerializer,
    LeaveRequestSerializer,
    MessageSerializer,
    NotificationSerializer,
    OvertimeSlipSerializer,
    PayrollItemSerializer,
    PayrollRunSerializer,
    PerformanceReviewSerializer,
    ShiftRosterSerializer,
    ShiftSwapSerializer,
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


class EmployeeListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = Employee.objects.all().order_by("last_name", "first_name")
    serializer_class = EmployeeSerializer
    owner_lookup = "user"

    def get_queryset(self):
        # OwnerQuerysetMixin (via super()) scopes non-staff to their own row.
        qs = super().get_queryset()
        q = (self.request.query_params.get("search") or "").strip()
        if q:
            qs = qs.filter(
                models.Q(first_name__icontains=q)
                | models.Q(last_name__icontains=q)
                | models.Q(email__icontains=q)
            )
        dept = (self.request.query_params.get("department") or "").strip()
        if dept:
            qs = qs.filter(department__name__iexact=dept)
        active = (self.request.query_params.get("is_active") or "").strip().lower()
        if active in ("true", "false"):
            qs = qs.filter(is_active=(active == "true"))
        return qs

    def get_permissions(self):
        # Self-service signup posts here logged-out; everything else stays
        # behind the default IsAuthenticated permission.
        if self.request.method == "POST":
            return [AllowAny()]
        return super().get_permissions()

    def post(self, request, *args, **kwargs):
        payload = request.data.copy()
        email = str(payload.get("email", "")).strip()
        if not email:
            return Response(
                {"error": "An employee email address is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        password = str(payload.get("password", "") or "")
        if password:
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password)
            except DjangoValidationError as exc:
                return Response(
                    {"error": exc.messages},
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
                employee = serializer.save(id=created_user_id)
                if password:
                    from django.contrib.auth.models import User

                    django_user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        first_name=payload.get("first_name", ""),
                        last_name=payload.get("last_name", ""),
                    )
                    employee.user = django_user
                    employee.save(update_fields=["user"])
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
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.resigned_at = timezone.localdate()
        instance.save(update_fields=["is_active", "resigned_at"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_active:
            instance.is_active = False
            instance.resigned_at = timezone.localdate()
            instance.save(update_fields=["is_active", "resigned_at"])
        purge_on = (
            instance.resigned_at + timedelta(days=30) if instance.resigned_at else None
        )
        # Fail-open: the resignation stands even if Supabase is down; purge retries.
        deauthed = True
        try:
            supabase.auth.admin.delete_user(str(instance.id))
        except Exception:
            deauthed = False
            logger.exception("resign: Supabase deauth failed for %s", instance.id)
        if not EmployeeAuditLog.objects.filter(
            employee=instance, action__icontains="resigned"
        ).exists():
            EmployeeAuditLog.objects.create(
                employee=instance,
                action=f"resigned {instance.resigned_at}, purge on {purge_on}, deauthed={deauthed}",
            )
        return Response(
            {
                "id": str(instance.id),
                "is_active": False,
                "resigned_at": instance.resigned_at,
                "purge_on": purge_on,
                "deauthed": deauthed,
            },
            status=status.HTTP_200_OK,
        )


class AttendanceListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
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
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise Conflict409("This change conflicts with an existing record.")


class AttendanceCorrectionListCreateView(
    OwnerQuerysetMixin, generics.ListCreateAPIView
):
    queryset = AttendanceCorrection.objects.all().order_by("-created_at")
    serializer_class = AttendanceCorrectionSerializer
    owner_lookup = "attendance__employee__user"


class AttendanceCorrectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AttendanceCorrection.objects.all()
    serializer_class = AttendanceCorrectionSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def patch(self, request, *args, **kwargs):
        if "status" not in request.data:
            return super().patch(request, *args, **kwargs)
        correction = self.get_object()
        new_status = request.data.get("status")
        if new_status not in ("Approved", "Rejected"):
            return Response(
                {"error": "status must be Approved or Rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status == correction.status:
            return Response(self.get_serializer(correction).data)
        if new_status == "Rejected":
            # Status-only update: anything else in the payload is ignored.
            correction.status = "Rejected"
            correction.save(update_fields=["status"])
            return Response(self.get_serializer(correction).data)
        with transaction.atomic():
            correction = AttendanceCorrection.objects.select_for_update().get(
                pk=correction.pk
            )
            if correction.status == "Approved":
                return Response(self.get_serializer(correction).data)
            row = Attendance.objects.select_for_update().get(
                pk=correction.attendance_id
            )
            update = {}
            if correction.proposed_clock_in is not None:
                update["clock_in"] = correction.proposed_clock_in
            if correction.proposed_clock_out is not None:
                update["clock_out"] = correction.proposed_clock_out
            attendance_update = AttendanceSerializer(row, data=update, partial=True)
            attendance_update.is_valid(raise_exception=True)
            attendance_update.save()
            correction.status = "Approved"
            correction.save(update_fields=["status"])
            EmployeeAuditLog.objects.create(
                employee=row.employee,
                action=(
                    f"attendance corrected {row.date}: "
                    f"clock_in {row.clock_in}, clock_out {row.clock_out}"
                ),
            )
            Notification.objects.create(
                employee=row.employee,
                kind="attendance",
                text=f"Attendance corrected for {row.date}",
            )
        return Response(self.get_serializer(correction).data)


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


class LeaveRequestListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = LeaveRequest.objects.all().order_by("-created_at")
    serializer_class = LeaveRequestSerializer


class LeaveRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]


class LeaveAllocationListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = LeaveAllocation.objects.all().order_by("-year", "leave_type")
    serializer_class = LeaveAllocationSerializer

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise Conflict409(
                "An allocation for this employee, type and year already exists."
            )


class LeaveAllocationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LeaveAllocation.objects.all()
    serializer_class = LeaveAllocationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]


def leave_balance(employee_id, leave_type, year):
    from datetime import date

    from .models import LEAVE_DEFAULTS

    allocated = LeaveAllocation.objects.filter(
        employee_id=employee_id, leave_type=leave_type, year=year
    ).first()
    total = allocated.days_total if allocated else LEAVE_DEFAULTS.get(leave_type, 0)
    used = 0
    for leave in LeaveRequest.objects.filter(
        employee_id=employee_id,
        leave_type=leave_type,
        status="Approved",
        start_date__year__lte=year,
        end_date__year__gte=year,
    ):
        start = max(leave.start_date, date(year, 1, 1))
        end = min(leave.end_date, date(year, 12, 31))
        used += (end - start).days + 1
    return {"allocated": float(total), "used": used, "remaining": float(total) - used}


class LeaveBalanceView(APIView):
    def get(self, request):
        emp = request.query_params.get("employee")
        year = request.query_params.get("year")
        if not emp or not year:
            return Response(
                {"error": "employee and year are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            year = int(year)
        except (TypeError, ValueError):
            return Response(
                {"error": "year must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        types = list(
            LeaveAllocation.objects.filter(employee_id=emp, year=year)
            .values_list("leave_type", flat=True)
            .distinct()
        ) or ["Vacation", "Sick"]
        return Response(
            {
                "employee": emp,
                "year": year,
                "balances": {t: leave_balance(emp, t, year) for t in types},
            }
        )


class OvertimeSlipListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = OvertimeSlip.objects.all().order_by("-created_at")
    serializer_class = OvertimeSlipSerializer

    def perform_create(self, serializer):
        raw_attendance = self.request.data.get("attendance")
        try:
            attendance = Attendance.objects.get(pk=raw_attendance)
        except (Attendance.DoesNotExist, ValueError, TypeError, DjangoValidationError):
            raise DRFValidationError({"attendance": "Attendance not found."})
        employee = serializer.validated_data.get("employee")
        if employee is None or attendance.employee_id != employee.id:
            raise DRFValidationError(
                {"attendance": "Attendance does not belong to this employee."}
            )
        if not attendance.clock_in or not attendance.clock_out:
            raise DRFValidationError({"attendance": "Attendance is incomplete."})
        worked = (attendance.clock_out - attendance.clock_in).total_seconds() / 3600
        hours = max(0, round(worked - 8, 2))
        serializer.save(hours=hours)


class OvertimeSlipDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = OvertimeSlip.objects.all()
    serializer_class = OvertimeSlipSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def perform_update(self, serializer):
        instance = serializer.instance
        instance.status = serializer.validated_data.get("status", instance.status)
        instance.save(update_fields=["status"])


class ShiftConflictView(APIView):
    def get(self, request):
        emp = request.query_params.get("employee")
        date = request.query_params.get("date")
        if not emp or not date:
            return Response(
                {"error": "employee and date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rosters = ShiftRoster.objects.filter(employee_id=emp, work_date=date)
        leaves = LeaveRequest.objects.filter(
            employee_id=emp,
            start_date__lte=date,
            end_date__gte=date,
            status="Approved",
        )
        return Response(
            {
                "date": date,
                "conflicts": [
                    {"roster": str(r.id), "leave": str(l.id)}
                    for r in rosters
                    for l in leaves
                ],
            }
        )


class ShiftRosterListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = ShiftRoster.objects.all().order_by("work_date", "start_time")
    serializer_class = ShiftRosterSerializer


class ShiftRosterDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftRoster.objects.all()
    serializer_class = ShiftRosterSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]


class ShiftSwapListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = ShiftSwap.objects.all().order_by("-created_at")
    serializer_class = ShiftSwapSerializer
    owner_lookup = "__swap_parties__"


class ShiftSwapDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftSwap.objects.all()
    serializer_class = ShiftSwapSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def perform_update(self, serializer):
        # Status-only update: any other patched fields are ignored.
        instance = serializer.instance
        serializer.save(
            requester_roster=instance.requester_roster,
            target_roster=instance.target_roster,
            reason=instance.reason,
            status=serializer.validated_data.get("status", instance.status),
        )

    def patch(self, request, *args, **kwargs):
        swap = self.get_object()
        serializer = self.get_serializer(swap, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data.get("status", swap.status)
        if swap.status != "Pending" and new_status != swap.status:
            return Response(
                {"error": "This swap has already been decided."},
                status=status.HTTP_409_CONFLICT,
            )
        if new_status == "Approved" and swap.status == "Pending":
            self._approve_swap(swap)
        elif new_status == "Rejected" and swap.status == "Pending":
            with transaction.atomic():
                swap.status = "Rejected"
                swap.save(update_fields=["status"])
                Notification.objects.create(
                    employee=swap.requester_roster.employee,
                    kind="shift",
                    text=(
                        "Swap rejected for "
                        f"{swap.requester_roster.work_date} "
                        f"({swap.requester_roster.shift_type} / "
                        f"{swap.target_roster.shift_type})"
                    ),
                )
        else:
            self.perform_update(serializer)
        return Response(
            self.get_serializer(self.get_object()).data,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _approve_swap(swap):
        with transaction.atomic():
            requester = ShiftRoster.objects.select_for_update().get(
                pk=swap.requester_roster_id
            )
            target = ShiftRoster.objects.select_for_update().get(
                pk=swap.target_roster_id
            )
            if not requester.employee_id or not target.employee_id:
                raise DRFValidationError("Both rosters must have an assigned employee.")
            new_requester_emp = target.employee_id
            new_target_emp = requester.employee_id
            requester.employee_id = new_requester_emp
            target.employee_id = new_target_emp
            requester.save(update_fields=["employee"])
            target.save(update_fields=["employee"])
            # Re-run the roster overlap guard against the post-swap state:
            # each holder has already released their old roster, so the two
            # swapped rows cannot clash with each other — only a genuine
            # third overlapping assignment raises Conflict409, which rolls
            # back the whole swap.
            for roster in (requester, target):
                guard = ShiftRosterSerializer(
                    instance=roster,
                    data={"employee": roster.employee_id},
                    partial=True,
                )
                guard.is_valid(raise_exception=True)
            swap.status = "Approved"
            swap.save(update_fields=["status"])
            for roster in (requester, target):
                Notification.objects.create(
                    employee_id=roster.employee_id,
                    kind="shift",
                    text=(
                        f"You are now on {roster.shift_type} "
                        f"{roster.work_date} (swap approved)"
                    ),
                )


class PayrollRunListCreateView(generics.ListCreateAPIView):
    queryset = PayrollRun.objects.all().order_by("-pay_period_start")
    serializer_class = PayrollRunSerializer


class PayrollRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollRun.objects.all()
    serializer_class = PayrollRunSerializer


class PayrollItemListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
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
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def perform_update(self, serializer):
        PayrollItemListCreateView._save_computed(serializer)


class PerformanceReviewListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = PerformanceReview.objects.all().order_by("-review_date")
    serializer_class = PerformanceReviewSerializer


class PerformanceReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]


class EmployeeAuditLogListView(generics.ListAPIView):
    queryset = EmployeeAuditLog.objects.all().order_by("-timestamp")
    serializer_class = EmployeeAuditLogSerializer


class SessionLoginView(APIView):
    permission_classes = [AllowAny]
    # Login must never 429: one office IP shares the anon quota, and a
    # throttled login locks everyone out. Brute-force hardening is deferred
    # to the token-lifecycle work (see round-4 findings).
    throttle_classes = []

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
        user = self.request.user
        name = user.get_full_name() or user.username
        key = self.request.data.get("conversation_key") or "general"
        serializer.save(conversation_key=key, sender_name=name)


class ClaimStatusListCreateView(generics.ListCreateAPIView):
    queryset = ClaimStatus.objects.all().order_by("claim_id")
    serializer_class = ClaimStatusSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        data = serializer.validated_data
        with transaction.atomic():
            obj, _ = ClaimStatus.objects.select_for_update().get_or_create(
                claim_id=data["claim_id"],
                defaults={"status": data["status"]},
            )
            if obj.status != data["status"]:
                obj.status = data["status"]
                obj.save(update_fields=["status"])
            serializer.instance = obj


class ExpenseClaimListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = ExpenseClaim.objects.all().order_by("-created_at")
    serializer_class = ExpenseClaimSerializer


class ExpenseClaimDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ExpenseClaim.objects.all()
    serializer_class = ExpenseClaimSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]


class NotificationListView(OwnerQuerysetMixin, generics.ListAPIView):
    queryset = Notification.objects.all().order_by("-created_at")
    serializer_class = NotificationSerializer


class NotificationMarkReadView(APIView):
    def patch(self, request, pk):
        note = get_object_or_404(Notification, pk=pk)
        user = request.user
        if not user.is_staff and getattr(note.employee, "user", None) != user:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        note.is_read = True
        note.save(update_fields=["is_read"])
        return Response(NotificationSerializer(note).data, status=status.HTTP_200_OK)


class PurgeRunView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        from io import StringIO

        from django.core.management import call_command

        try:
            days = int(request.data.get("days", 30))
        except (TypeError, ValueError):
            return Response(
                {"error": "days must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dry = bool(request.data.get("dry_run", True))
        out, err = StringIO(), StringIO()
        call_command("purge_resigned", days=days, dry_run=dry, stdout=out, stderr=err)
        log = out.getvalue() + err.getvalue()
        lines = log.splitlines()
        return Response(
            {
                "dry_run": dry,
                "would_purge": sum(
                    1 for line in lines if line.startswith("would purge ")
                ),
                "purged": sum(1 for line in lines if line.startswith("purged ")),
                "log": log,
            }
        )
