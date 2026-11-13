"""Advisory estimates from recorded work and HR-defined policies.

Breaks have a duration but no scheduled placement in the roster. Partial
coverage of such a shift is therefore explicitly marked as indeterminate.
"""
import hashlib
import json
from datetime import datetime, time, timedelta, timezone as datetime_timezone
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from .models import Attendance, LeaveRequest, PayEstimate, PayEstimateAdjustment, PayEstimateLine, PayEstimatePolicy, PayEstimateRevision, ShiftRoster

ALGORITHM_VERSION = "1"
ZERO = Decimal("0")
HOUR = Decimal("3600")


def _seconds(delta):
    return Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / Decimal(1000000)


def _money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _dt(day, at=time.min):
    return timezone.make_aware(datetime.combine(day, at), timezone.get_current_timezone()).astimezone(datetime_timezone.utc)


def _json(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _snapshot(estimate):
    start = _dt(estimate.period_start)
    end = _dt(estimate.period_end + timedelta(days=1))
    attendance = Attendance.objects.filter(employee_id=estimate.employee_id).filter(
        Q(date__range=(estimate.period_start - timedelta(days=1), estimate.period_end + timedelta(days=1))) |
        Q(clock_in__lt=end, clock_out__gte=start) | Q(clock_in__lt=end, clock_out__isnull=True)
    ).order_by("date", "id")
    shifts = ShiftRoster.objects.filter(employee_id=estimate.employee_id, work_date__range=(estimate.period_start - timedelta(days=1), estimate.period_end)).order_by("work_date", "id")
    leaves = LeaveRequest.objects.filter(employee_id=estimate.employee_id, start_date__lte=estimate.period_end, end_date__gte=estimate.period_start).order_by("start_date", "id")
    policies = PayEstimatePolicy.objects.filter(effective_date__lte=estimate.period_end).order_by("effective_date", "created_at", "id")
    def rows(query, fields):
        return [{name: _json(getattr(row, name)) if getattr(row, name) is not None else None for name in fields} for row in query]
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "timezone": str(timezone.get_current_timezone()),
        "employee_id": str(estimate.employee_id), "employee_name": str(estimate.employee), "employee_code": estimate.employee.employee_id,
        "period_start": str(estimate.period_start), "period_end": str(estimate.period_end),
        "hourly_rate": str(_money(Decimal(estimate.hourly_rate))), "deductions": str(_money(Decimal(estimate.deductions))),
        "attendance": rows(attendance, ("id", "date", "clock_in", "clock_out")),
        "shifts": rows(shifts, ("id", "work_date", "start_time", "end_time", "break_mins")),
        "leaves": rows(leaves, ("id", "start_date", "end_date", "leave_type", "status")),
        "policies": [{"id": str(p.id), "effective_date": str(p.effective_date), "created_at": p.created_at.isoformat(), "overtime_threshold_hours": str(p.overtime_threshold_hours) if p.overtime_threshold_hours is not None else None, "overtime_multiplier": str(p.overtime_multiplier) if p.overtime_multiplier is not None else None, "paid_leave_types": p.paid_leave_types} for p in policies],
    }


def _fingerprint(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def source_fingerprint(estimate):
    return _fingerprint(_snapshot(estimate))


def _merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _intersection_seconds(intervals, start, end):
    return sum((_seconds(min(b, end) - max(a, start)) for a, b in intervals if a < end and b > start), ZERO)


@transaction.atomic
def create_revision(estimate, actor=None):
    estimate = PayEstimate.objects.select_for_update().get(pk=estimate.pk)
    snapshot = _snapshot(estimate)
    rate = Decimal(snapshot["hourly_rate"])
    warnings, lines, adjustments = [], [], []

    def warn(day, code, message):
        warnings.append({"date": str(day), "code": code, "message": message})

    day = estimate.period_start
    while day <= estimate.period_end:
        start, end = _dt(day), _dt(day + timedelta(days=1))
        policies = [p for p in snapshot["policies"] if p["effective_date"] <= str(day)]
        policy = policies[-1] if policies else None
        intervals, source_ids = [], []
        invalid_attendance = False
        for record in snapshot["attendance"]:
            cin = parse_datetime(record["clock_in"]) if record["clock_in"] else None
            cout = parse_datetime(record["clock_out"]) if record["clock_out"] else None
            if not cin or not cout or timezone.is_naive(cin) or timezone.is_naive(cout) or cout <= cin:
                open_could_overlap = cin is not None and not timezone.is_naive(cin) and cout is None and cin < end
                invalid_start_in_day = cin is not None and not timezone.is_naive(cin) and start <= cin < end
                if record["date"] == str(day) or open_could_overlap or invalid_start_in_day:
                    warn(day, "invalid_attendance", "Attendance is open or has invalid times.")
                    invalid_attendance = True
                continue
            if cin < end and cout > start:
                intervals.append((max(start, cin), min(end, cout)))
                source_ids.append(record["id"])
        intervals = _merge(intervals)
        worked = sum((_seconds(b - a) for a, b in intervals), ZERO)
        schedules = [s for s in snapshot["shifts"] if s["work_date"] == str(day)]
        # Previous-day overnight shifts cannot be allocated reliably from a
        # duration-only break; flag rather than silently guessing.
        prior_overnight = [s for s in snapshot["shifts"] if s["work_date"] == str(day - timedelta(days=1)) and parse_time(s["end_time"]) <= parse_time(s["start_time"])]
        if prior_overnight:
            warn(day, "overnight_shift", "An overnight shift needs manual review.")
        day_leaves = [l for l in snapshot["leaves"] if l["status"] == "Approved" and l["start_date"] <= str(day) <= l["end_date"]]
        paid_leaves = [l for l in day_leaves if policy and l["leave_type"] in policy["paid_leave_types"]]
        if schedules and not intervals and not day_leaves:
            warn(day, "missing_attendance", "The scheduled day has no completed attendance or approved leave.")
        if day_leaves and policy is None:
            warn(day, "leave_not_assessed", "Paid leave cannot be assessed without an effective policy.")
        if (worked or paid_leaves) and not schedules:
            warn(day, "missing_schedule", "A schedule is required to assess breaks and paid leave.")
        shift_intervals = []
        for shift in schedules:
            shift_start, shift_end = parse_time(shift["start_time"]), parse_time(shift["end_time"])
            if shift_end <= shift_start:
                warn(day, "overnight_shift", "An overnight shift needs manual review.")
                continue
            a, b = _dt(day, shift_start), _dt(day, shift_end)
            duration, break_seconds = _seconds(b - a), Decimal(shift["break_mins"]) * 60
            if break_seconds < 0 or break_seconds > duration:
                warn(day, "invalid_break", "The scheduled break duration is invalid.")
                continue
            shift_intervals.append((a, b, break_seconds, shift["id"]))
        shift_intervals.sort()
        if any(shift_intervals[i][0] < shift_intervals[i-1][1] for i in range(1, len(shift_intervals))):
            warn(day, "overlapping_schedules", "Overlapping schedules need manual review.")
            shift_intervals = []
        breaks, leave_seconds = ZERO, ZERO
        for a, b, break_seconds, shift_id in shift_intervals:
            duration = _seconds(b - a)
            overlap = _intersection_seconds(intervals, a, b)
            if break_seconds and ZERO < overlap < duration:
                warn(day, "ambiguous_break", "The break timing is unknown for a partially worked shift.")
                continue
            if overlap == duration:
                breaks += break_seconds
            if paid_leaves and not invalid_attendance:
                leave_seconds += max(ZERO, duration - break_seconds - overlap + (break_seconds if overlap == duration else ZERO))
        paid_seconds = max(ZERO, worked - breaks)
        if worked:
            lines.append({"work_date": day, "attendance_id": source_ids[0] if len(source_ids) == 1 else None,
                          "worked_seconds": worked, "break_seconds": breaks, "paid_seconds": paid_seconds,
                          "base_amount": _money(paid_seconds / HOUR * rate),
                          "source": {"attendance_ids": source_ids, "shift_ids": [s[3] for s in shift_intervals]}})
            if not policy or policy["overtime_threshold_hours"] is None or policy["overtime_multiplier"] is None:
                warn(day, "overtime_not_assessed", "Overtime: Not assessed; no effective overtime policy is configured.")
            else:
                hours = max(ZERO, paid_seconds / HOUR - Decimal(policy["overtime_threshold_hours"]))
                if hours:
                    multiplier = Decimal(policy["overtime_multiplier"])
                    adjustments.append({"kind": "OVERTIME", "work_date": day, "hours": hours, "hourly_rate": rate, "multiplier": multiplier,
                                        "amount": _money(hours * rate * (multiplier - 1)), "source_key": f"overtime:{day}"})
        if paid_leaves and leave_seconds > 0:
            hours = leave_seconds / HOUR
            adjustments.append({"kind": "PAID_LEAVE", "work_date": day, "hours": hours, "hourly_rate": rate, "multiplier": Decimal("1"),
                                "amount": _money(hours * rate), "source_key": f"leave:{day}"})
        day += timedelta(days=1)

    revision = PayEstimateRevision.objects.create(estimate=estimate, number=estimate.current_revision + 1,
        input_snapshot=snapshot, fingerprint=_fingerprint(snapshot), base_amount=_money(sum((line["paid_seconds"] for line in lines), ZERO) / HOUR * rate),
        deductions=estimate.deductions, is_complete=not warnings, warnings=warnings)
    PayEstimateLine.objects.bulk_create([PayEstimateLine(revision=revision, **line) for line in lines])
    PayEstimateAdjustment.objects.bulk_create([PayEstimateAdjustment(revision=revision, **adjustment) for adjustment in adjustments])
    estimate.current_revision = revision.number
    estimate.save(update_fields=["current_revision", "updated_at"])
    return revision
