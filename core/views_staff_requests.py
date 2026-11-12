"""Staff schedules and requests, with one guarded path for each decision."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import Conflict409
from .models import (Attendance, AttendanceCorrection, Employee, EmployeeAuditLog,
                     OvertimeSlip, PayEstimatePolicy, ShiftRoster, ShiftSwap)
from .notifications import notify_employee
from .pay_estimates import _dt, _intersection_seconds, _merge, _seconds
from .permissions import is_staff_or_hr
from .serializers import (AttendanceCorrectionSerializer, OvertimeSlipSerializer,
                          ShiftRosterSerializer, ShiftSwapSerializer)


def active_employee(user):
    if not user.is_active:
        raise PermissionDenied("An active account is required.")
    employee = Employee.objects.filter(user=user).first()
    if employee and (not employee.is_active or employee.status != Employee.OnboardingStatus.ACTIVE):
        raise PermissionDenied("An active employee profile is required.")
    if not employee and not is_staff_or_hr(user):
        raise PermissionDenied("An active employee profile is required.")
    return employee


class ActiveAccount(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        active_employee(request.user)
        return True


class ScopedMixin:
    permission_classes = [IsAuthenticated, ActiveAccount]
    owner_field = "employee"

    def get_queryset(self):
        qs = super().get_queryset()
        if is_staff_or_hr(self.request.user):
            return qs
        employee = active_employee(self.request.user)
        if self.owner_field == "swap":
            return qs.filter(Q(requester_employee=employee) | Q(target_employee=employee))
        return qs.filter(**{self.owner_field: employee})


def require_hr(user):
    active_employee(user)
    if not is_staff_or_hr(user):
        raise PermissionDenied("Only HR staff can decide this request.")


def audit(employee, user, action):
    EmployeeAuditLog.objects.create(employee=employee, action=f"{action} by user {user.pk}.")


def only_decision(data):
    if set(data.keys()) != {"status"} or data.get("status") not in ("Approved", "Rejected"):
        raise ValidationError({"status": "Supply only status: Approved or Rejected."})
    return data["status"]


def ensure_pending(obj):
    if obj.status != "Pending":
        raise Conflict409("This request has already been decided.")


def requested_date(value, field):
    try:
        day = parse_date(value)
    except (TypeError, ValueError):
        day = None
    if not day:
        raise ValidationError({field: "Use YYYY-MM-DD."})
    return day


def valid_roster_parties(a, b):
    if not a.employee_id or not b.employee_id or not a.work_date or not b.work_date:
        raise ValidationError("Both shifts must have an assigned employee and date.")
    if a.employee_id == b.employee_id or a.work_date != b.work_date:
        raise ValidationError("Shifts must be on the same date and belong to different employees.")
    for roster in (a, b):
        employee = roster.employee
        if not employee.is_active or employee.status != Employee.OnboardingStatus.ACTIVE or not employee.user_id or not employee.user.is_active:
            raise ValidationError("Both shifts must belong to active employees with active accounts.")


@transaction.atomic
def decide_swap(pk, decision, user):
    active_employee(user)
    swap = get_object_or_404(ShiftSwap.objects.select_for_update(), pk=pk)
    if not is_staff_or_hr(user) and (not swap.requester_employee_id or not swap.target_employee_id or swap.target_employee.user_id != user.pk):
        raise PermissionDenied("Only the original target employee or HR staff can decide this swap.")
    ensure_pending(swap)
    if decision not in ("Approved", "Rejected"):
        raise ValidationError({"decision": "Choose Approved or Rejected."})
    rosters = {r.pk: r for r in ShiftRoster.objects.select_for_update().select_related("employee__user").filter(pk__in=[swap.requester_roster_id, swap.target_roster_id]).order_by("pk")}
    a, b = rosters.get(swap.requester_roster_id), rosters.get(swap.target_roster_id)
    if not a or not b:
        raise ValidationError("Both shifts must exist.")
    if decision == "Approved":
        valid_roster_parties(a, b)
        if not swap.requester_employee_id or not swap.target_employee_id or a.employee_id != swap.requester_employee_id or b.employee_id != swap.target_employee_id:
            raise Conflict409("The original participants are unavailable or their shifts changed; review this request.")
        # Lock both employees, serializing decisions involving other shifts.
        list(Employee.objects.select_for_update().filter(pk__in=[a.employee_id, b.employee_id]).order_by("pk"))
        for roster, new_employee in ((a, b.employee_id), (b, a.employee_id)):
            if ShiftRoster.objects.filter(employee_id=new_employee, work_date=roster.work_date, start_time__lt=roster.end_time, end_time__gt=roster.start_time).exclude(pk__in=[a.pk, b.pk]).exists():
                raise Conflict409("The swap would overlap another shift.")
        a.employee_id, b.employee_id = b.employee_id, a.employee_id
        a.save(update_fields=["employee"])
        b.save(update_fields=["employee"])
    # Signal sends one deduplicated notification per party.
    swap.requester_roster, swap.target_roster = a, b
    swap.status = decision
    swap.save(update_fields=["status"])
    audit(a.employee, user, f"Shift swap {swap.pk} {decision.lower()}")
    return swap


@transaction.atomic
def decide_correction(pk, decision, user):
    require_hr(user)
    correction = get_object_or_404(AttendanceCorrection.objects.select_for_update(), pk=pk)
    ensure_pending(correction)
    if decision not in ("Approved", "Rejected"):
        raise ValidationError({"decision": "Choose Approved or Rejected."})
    attendance = Attendance.objects.select_for_update().select_related("employee").get(pk=correction.attendance_id)
    if decision == "Approved":
        clock_in = correction.proposed_clock_in or attendance.clock_in
        clock_out = correction.proposed_clock_out or attendance.clock_out
        if clock_in and clock_out and clock_out <= clock_in:
            raise ValidationError("The proposed clock out must be after clock in.")
        attendance.clock_in, attendance.clock_out = clock_in, clock_out
        attendance.save(update_fields=["clock_in", "clock_out"])
    correction.status = decision
    correction.save(update_fields=["status"])
    audit(attendance.employee, user, f"Attendance correction {correction.pk} {decision.lower()}")
    notify_employee(attendance.employee, f"Attendance correction {decision.lower()} for {attendance.date}", "attendance", "attendance_correction", correction.pk, f"correction:{correction.pk}:{decision}:{attendance.employee_id}")
    return correction


@transaction.atomic
def decide_overtime(pk, decision, user):
    require_hr(user)
    slip = get_object_or_404(OvertimeSlip.objects.select_for_update().select_related("employee"), pk=pk)
    ensure_pending(slip)
    if decision not in ("Approved", "Rejected"):
        raise ValidationError({"decision": "Choose Approved or Rejected."})
    slip.status = decision
    slip.save(update_fields=["status"])
    audit(slip.employee, user, f"Overtime request {slip.pk} {decision.lower()}")
    return slip


def overtime_values(attendance):
    day = attendance.date
    policy = PayEstimatePolicy.objects.filter(effective_date__lte=day).order_by("-effective_date", "-created_at", "-id").first()
    if not policy or policy.overtime_threshold_hours is None or policy.overtime_multiplier is None:
        raise ValidationError("Configure an effective overtime policy before requesting overtime.")
    if policy.overtime_multiplier > Decimal("99.99"):
        raise ValidationError("The configured overtime multiplier cannot be represented on a slip; update the policy.")
    if not attendance.clock_in or not attendance.clock_out or attendance.clock_out <= attendance.clock_in:
        raise ValidationError({"attendance": "Completed attendance with valid times is required."})
    start, end = _dt(day), _dt(day + timedelta(days=1))
    if attendance.clock_in < start or attendance.clock_out > end:
        raise ValidationError("Overnight attendance needs manual review.")
    shifts = list(ShiftRoster.objects.filter(employee=attendance.employee, work_date=day).order_by("start_time"))
    if not shifts:
        raise ValidationError("A schedule is required to assess breaks and overtime.")
    if ShiftRoster.objects.filter(employee=attendance.employee, work_date=day-timedelta(days=1), end_time__lte=F('start_time')).exists():
        raise ValidationError("An overnight shift needs manual review.")
    if Attendance.objects.filter(employee=attendance.employee, date=day, clock_in__isnull=True).exists():
        raise ValidationError("Open or invalid attendance needs manual review.")
    intervals = []
    for row in Attendance.objects.filter(employee=attendance.employee, clock_in__lt=end).filter(Q(clock_out__gt=start) | Q(clock_out__isnull=True)):
        if not row.clock_out or row.clock_out <= row.clock_in:
            raise ValidationError("Open or invalid attendance needs manual review.")
        intervals.append((max(start, row.clock_in), min(end, row.clock_out)))
    intervals = _merge(intervals)
    worked = sum((_seconds(b-a) for a,b in intervals), Decimal(0))
    breaks = Decimal(0)
    previous_end = None
    for shift in shifts:
        if shift.end_time <= shift.start_time:
            raise ValidationError("An overnight shift needs manual review.")
        a, b = _dt(day, shift.start_time), _dt(day, shift.end_time)
        duration, pause = _seconds(b-a), Decimal(shift.break_mins) * 60
        if previous_end and a < previous_end:
            raise ValidationError("Overlapping schedules need manual review.")
        previous_end = b
        if pause < 0 or pause > duration:
            raise ValidationError("The scheduled break duration is invalid.")
        overlap = _intersection_seconds(intervals, a, b)
        if pause and 0 < overlap < duration:
            raise ValidationError("A partially worked shift has an ambiguous break; manual review is required.")
        if overlap == duration:
            breaks += pause
    hours = max(Decimal(0), max(Decimal(0), worked-breaks)/Decimal(3600)-policy.overtime_threshold_hours)
    return (hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), policy.overtime_multiplier.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class ShiftRosterListCreateView(ScopedMixin, generics.ListCreateAPIView):
    queryset = ShiftRoster.objects.select_related("employee").order_by("work_date", "start_time")
    serializer_class = ShiftRosterSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for param, lookup in (("work_date", "work_date"), ("start_date", "work_date__gte"), ("end_date", "work_date__lte")):
            value = self.request.query_params.get(param)
            if value:
                day = requested_date(value, param)
                qs = qs.filter(**{lookup: day})
        return qs

    def perform_create(self, serializer):
        require_hr(self.request.user)
        serializer.save()


class ShiftRosterDetailView(ScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftRoster.objects.all()
    serializer_class = ShiftRosterSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            qs = qs.select_for_update()
        return qs

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def _guard(self):
        require_hr(self.request.user)
        obj = self.get_object()
        if ShiftSwap.objects.filter(status="Pending").filter(Q(requester_roster=obj) | Q(target_roster=obj)).exists():
            raise Conflict409("Decide the pending swap before changing this shift.")

    def perform_update(self, serializer):
        self._guard()
        serializer.save()

    def perform_destroy(self, instance):
        self._guard()
        instance.delete()


class AvailableShiftRosterView(APIView):
    permission_classes = [IsAuthenticated, ActiveAccount]

    def get(self, request):
        day = requested_date(request.query_params.get("work_date", ""), "work_date")
        employee = active_employee(request.user)
        qs = ShiftRoster.objects.filter(work_date=day, employee__is_active=True, employee__status=Employee.OnboardingStatus.ACTIVE, employee__user__is_active=True).exclude(employee=employee).select_related("employee").order_by("start_time", "pk")
        qs = qs.exclude(Q(swap_requests__status="Pending") | Q(swap_targets__status="Pending")).distinct()
        return Response([{"id": str(r.pk), "employee_name": str(r.employee), "work_date": r.work_date, "start_time": r.start_time, "end_time": r.end_time, "shift_type": r.shift_type} for r in qs])


class ShiftSwapListCreateView(ScopedMixin, generics.ListCreateAPIView):
    queryset = ShiftSwap.objects.select_related("requester_employee", "target_employee", "requester_roster", "target_roster").order_by("-created_at")
    serializer_class = ShiftSwapSerializer
    owner_field = "swap"

    @transaction.atomic
    def perform_create(self, serializer):
        if "status" in self.request.data:
            raise ValidationError({"status": "A new request must be pending."})
        employee = active_employee(self.request.user)
        a, b = serializer.validated_data["requester_roster"], serializer.validated_data["target_roster"]
        locked = {r.pk: r for r in ShiftRoster.objects.select_for_update().select_related("employee__user").filter(pk__in=[a.pk, b.pk]).order_by("pk")}
        a, b = locked[a.pk], locked[b.pk]
        valid_roster_parties(a, b)
        if not employee or a.employee_id != employee.pk:
            raise PermissionDenied("You can only request a swap for your own shift.")
        if ShiftSwap.objects.filter(status="Pending").filter(Q(requester_roster__in=[a,b]) | Q(target_roster__in=[a,b])).exists():
            raise Conflict409("A swap is already pending for this roster.")
        obj = serializer.save(requester_roster=a, target_roster=b, requester_employee=a.employee, target_employee=b.employee, status="Pending")
        audit(employee, self.request.user, f"Shift swap {obj.pk} requested")


class DecisionDetail(ScopedMixin, generics.RetrieveUpdateAPIView):
    decision_function = None

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        decision = only_decision(request.data)
        obj = self.decision_function(obj.pk, decision, request.user)
        return Response(self.get_serializer(obj).data)


class ShiftSwapDetailView(DecisionDetail):
    queryset = ShiftSwap.objects.all()
    serializer_class = ShiftSwapSerializer
    owner_field = "swap"
    decision_function = staticmethod(decide_swap)


class AttendanceCorrectionListCreateView(ScopedMixin, generics.ListCreateAPIView):
    queryset = AttendanceCorrection.objects.select_related("attendance__employee").order_by("-created_at")
    serializer_class = AttendanceCorrectionSerializer
    owner_field = "attendance__employee"

    def perform_create(self, serializer):
        if "status" in self.request.data:
            raise ValidationError({"status": "A new request must be pending."})
        employee = active_employee(self.request.user)
        attendance = serializer.validated_data["attendance"]
        if not employee or attendance.employee_id != employee.pk:
            raise PermissionDenied("You can only request corrections for your own attendance.")
        obj = serializer.save(status="Pending")
        audit(employee, self.request.user, f"Attendance correction {obj.pk} requested")


class AttendanceCorrectionDetailView(DecisionDetail):
    queryset = AttendanceCorrection.objects.all()
    serializer_class = AttendanceCorrectionSerializer
    owner_field = "attendance__employee"
    decision_function = staticmethod(decide_correction)


class OvertimeSlipListCreateView(ScopedMixin, generics.ListCreateAPIView):
    queryset = OvertimeSlip.objects.all().order_by("-created_at")
    serializer_class = OvertimeSlipSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        if "status" in self.request.data or "hours" in self.request.data or "multiplier" in self.request.data:
            raise ValidationError("Status, hours and multiplier are determined by the system.")
        employee = active_employee(self.request.user)
        attendance = Attendance.objects.select_for_update().get(pk=serializer.validated_data["attendance"].pk)
        if not employee or attendance.employee_id != employee.pk:
            raise PermissionDenied("You can only request overtime for your own attendance.")
        supplied_employee = serializer.validated_data.get("employee")
        if supplied_employee and supplied_employee.pk != employee.pk:
            raise ValidationError({"employee": "Employee must match attendance."})
        supplied_date = serializer.validated_data.get("date")
        if supplied_date and supplied_date != attendance.date:
            raise ValidationError({"date": "Date must match attendance."})
        hours, multiplier = overtime_values(attendance)
        if hours <= 0:
            raise ValidationError("This attendance has no overtime under the effective policy.")
        if OvertimeSlip.objects.filter(attendance=attendance).exists():
            raise Conflict409("An overtime request already exists for this attendance.")
        try:
            obj = serializer.save(employee=employee, attendance=attendance, date=attendance.date, hours=hours, multiplier=multiplier, status="Pending")
        except IntegrityError:
            raise Conflict409("An overtime request already exists for this attendance.")
        audit(employee, self.request.user, f"Overtime request {obj.pk} submitted")


class OvertimeSlipDetailView(DecisionDetail):
    queryset = OvertimeSlip.objects.all()
    serializer_class = OvertimeSlipSerializer
    decision_function = staticmethod(decide_overtime)
