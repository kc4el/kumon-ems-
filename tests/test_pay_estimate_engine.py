from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Attendance, Employee, LeaveRequest, PayEstimate, PayEstimateAdjustment, PayEstimateLine, PayEstimatePolicy, PayEstimateRevision, ShiftRoster
from core.pay_estimates import create_revision, source_fingerprint


@override_settings(TIME_ZONE="UTC")
class PayEstimateEngineTests(TestCase):
    def setUp(self):
        self.day = date(2026, 1, 12)
        self.employee = Employee.objects.create(first_name="A", last_name="B", email="a@example.com")
        self.estimate = PayEstimate.objects.create(employee=self.employee, period_start=self.day, period_end=self.day, hourly_rate=Decimal("100"))

    def at(self, hour, minute=0, second=0):
        return timezone.make_aware(datetime.combine(self.day, time(hour, minute, second)))

    def shift(self, start=9, end=18, break_mins=0):
        return ShiftRoster.objects.create(employee=self.employee, work_date=self.day, start_time=time(start), end_time=time(end), break_mins=break_mins)

    def attendance(self, start=9, end=18):
        return Attendance.objects.create(employee=self.employee, date=self.day, clock_in=self.at(start), clock_out=self.at(end))

    def policy(self, threshold="8", multiplier="1.25", types=None):
        return PayEstimatePolicy.objects.create(effective_date=self.day, overtime_threshold_hours=threshold, overtime_multiplier=multiplier, paid_leave_types=types or [])

    def test_all_work_paid_at_base_plus_only_overtime_premium(self):
        self.shift()
        self.attendance()
        self.policy()
        revision = create_revision(self.estimate)
        self.assertTrue(revision.is_complete)
        self.assertEqual(revision.base_amount, Decimal("900.00"))
        adjustment = revision.adjustments.get()
        self.assertEqual((adjustment.kind, adjustment.hours, adjustment.amount, adjustment.status), ("OVERTIME", Decimal("1"), Decimal("25.00"), "Pending"))

    def test_complete_shift_deducts_break_but_partial_shift_is_incomplete(self):
        self.shift(break_mins=60)
        attendance = self.attendance()
        self.policy()
        first = create_revision(self.estimate)
        self.assertEqual(first.base_amount, Decimal("800.00"))
        self.assertEqual(first.lines.get().break_seconds, Decimal("3600"))
        attendance.clock_out = self.at(15)
        attendance.save()
        second = create_revision(self.estimate)
        self.assertFalse(second.is_complete)
        self.assertIn("ambiguous_break", [w["code"] for w in second.warnings])

    def test_invalid_break_and_open_attendance_are_reported(self):
        self.shift(break_mins=600)
        self.attendance()
        self.policy()
        revision = create_revision(self.estimate)
        self.assertIn("invalid_break", [w["code"] for w in revision.warnings])
        Attendance.objects.update(clock_out=None)
        revision = create_revision(self.estimate)
        self.assertIn("invalid_attendance", [w["code"] for w in revision.warnings])

    def test_prior_day_open_attendance_is_incomplete(self):
        Attendance.objects.create(employee=self.employee, date=self.day - timedelta(days=2), clock_in=self.at(0) - timedelta(days=2))
        revision = create_revision(self.estimate)
        self.assertFalse(revision.is_complete)
        self.assertIn("invalid_attendance", [w["code"] for w in revision.warnings])

    def test_missing_attendance_on_scheduled_day_is_incomplete(self):
        self.shift()
        revision = create_revision(self.estimate)
        self.assertFalse(revision.is_complete)
        self.assertIn("missing_attendance", [w["code"] for w in revision.warnings])

    def test_open_attendance_does_not_produce_unverified_leave_pay(self):
        self.shift()
        Attendance.objects.create(employee=self.employee, date=self.day, clock_in=self.at(9))
        self.policy(types=["Sick"])
        LeaveRequest.objects.create(employee=self.employee, start_date=self.day, end_date=self.day, leave_type="Sick", status="Approved", reason="")
        revision = create_revision(self.estimate)
        self.assertFalse(revision.is_complete)
        self.assertFalse(revision.adjustments.filter(kind="PAID_LEAVE").exists())

    def test_approved_leave_excludes_work_and_duplicate_requests(self):
        self.shift()
        self.attendance(start=9, end=12)
        self.policy(types=["Sick"])
        for unused in range(2):
            LeaveRequest.objects.create(employee=self.employee, start_date=self.day, end_date=self.day, leave_type="Sick", status="Approved", reason="")
        LeaveRequest.objects.create(employee=self.employee, start_date=self.day, end_date=self.day, leave_type="Sick", status="Pending", reason="")
        revision = create_revision(self.estimate)
        self.assertEqual(revision.base_amount, Decimal("300.00"))
        leave = revision.adjustments.get(kind="PAID_LEAVE")
        self.assertEqual((leave.hours, leave.amount), (Decimal("6"), Decimal("600.00")))

    def test_no_policy_not_assessed_and_missing_schedule_is_incomplete(self):
        self.attendance()
        revision = create_revision(self.estimate)
        self.assertFalse(revision.is_complete)
        self.assertEqual(set(w["code"] for w in revision.warnings), {"overtime_not_assessed", "missing_schedule"})
        self.assertFalse(revision.adjustments.exists())

    def test_snapshot_change_creates_new_revision_without_changing_approval(self):
        self.shift()
        attendance = self.attendance()
        self.policy()
        first = create_revision(self.estimate)
        first.adjustments.update(status="Approved")
        self.assertEqual(first.fingerprint, source_fingerprint(self.estimate))
        attendance.clock_out = self.at(17)
        attendance.save()
        self.assertNotEqual(first.fingerprint, source_fingerprint(self.estimate))
        second = create_revision(self.estimate)
        self.assertEqual(second.number, 2)
        self.assertEqual(first.adjustments.get().status, "Approved")
        self.assertEqual(second.base_amount, Decimal("800.00"))

    def test_money_rounds_half_up_after_full_precision_seconds(self):
        self.shift()
        Attendance.objects.create(employee=self.employee, date=self.day, clock_in=self.at(9), clock_out=self.at(9, 0, 18))
        self.estimate.hourly_rate = Decimal("1.00")
        self.estimate.save()
        self.policy()
        revision = create_revision(self.estimate)
        self.assertEqual(revision.base_amount, Decimal("0.01"))

    def test_revision_total_rounds_aggregate_and_daily_lines_stay_traceable(self):
        self.estimate.period_end = self.day + timedelta(days=2)
        self.estimate.hourly_rate = Decimal("1.00")
        self.estimate.save()
        self.policy()
        for offset in range(3):
            day = self.day + timedelta(days=offset)
            ShiftRoster.objects.create(employee=self.employee, work_date=day, start_time=time(9), end_time=time(18), break_mins=0)
            start = timezone.make_aware(datetime.combine(day, time(9)))
            Attendance.objects.create(employee=self.employee, date=day, clock_in=start, clock_out=start + timedelta(minutes=20))
        revision = create_revision(self.estimate)
        self.assertEqual(revision.base_amount, Decimal("1.00"))
        self.assertEqual(sum((line.base_amount for line in revision.lines.all()), Decimal("0")), Decimal("0.99"))
        self.assertEqual(revision.input_snapshot["employee_name"], "A B")

    def test_new_policy_on_same_date_supersedes_and_changes_fingerprint(self):
        self.shift()
        self.attendance()
        self.policy()
        first = create_revision(self.estimate)
        self.policy(threshold="8", multiplier="1.50")
        self.assertNotEqual(first.fingerprint, source_fingerprint(self.estimate))
        second = create_revision(self.estimate)
        self.assertEqual(second.adjustments.get().amount, Decimal("50.00"))

    @override_settings(TIME_ZONE="America/New_York")
    def test_daylight_saving_counts_elapsed_time(self):
        from zoneinfo import ZoneInfo
        day = date(2026, 3, 8)
        self.estimate.period_start = self.estimate.period_end = day
        self.estimate.save()
        PayEstimatePolicy.objects.create(effective_date=day, overtime_threshold_hours="8", overtime_multiplier="1.25")
        ShiftRoster.objects.create(employee=self.employee, work_date=day, start_time=time(1), end_time=time(4), break_mins=0)
        Attendance.objects.create(employee=self.employee, date=day,
            clock_in=datetime(2026, 3, 8, 1, tzinfo=ZoneInfo("America/New_York")),
            clock_out=datetime(2026, 3, 8, 4, tzinfo=ZoneInfo("America/New_York")))
        revision = create_revision(self.estimate)
        self.assertEqual(revision.base_amount, Decimal("200.00"))

    def test_employee_retention_purge_removes_estimate_records(self):
        self.shift()
        self.attendance()
        self.policy()
        create_revision(self.estimate)
        self.employee.delete()
        for model in (PayEstimate, PayEstimateRevision, PayEstimateLine, PayEstimateAdjustment):
            self.assertFalse(model.objects.exists())
