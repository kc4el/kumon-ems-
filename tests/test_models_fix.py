from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone

from core.models import Attendance, Employee, OvertimeSlip


class OvertimeSlipEmployeeMatchTests(TestCase):
    def setUp(self):
        self.emp_a = Employee.objects.create(
            first_name="Amy", last_name="Alba", email="ot-a@example.com"
        )
        self.emp_b = Employee.objects.create(
            first_name="Bob", last_name="Baker", email="ot-b@example.com"
        )
        self.attendance = Attendance.objects.create(
            employee=self.emp_a, date=date(2026, 9, 10)
        )

    def test_clean_passes_when_employee_matches_attendance(self):
        slip = OvertimeSlip(
            employee=self.emp_a,
            attendance=self.attendance,
            date=date(2026, 9, 10),
            hours=Decimal("2.00"),
        )
        slip.full_clean()

    def test_clean_rejects_mismatched_employee(self):
        slip = OvertimeSlip(
            employee=self.emp_b,
            attendance=self.attendance,
            date=date(2026, 9, 10),
            hours=Decimal("2.00"),
        )
        with self.assertRaises(ValidationError):
            slip.full_clean()


class AttendanceOpenPerDayTests(TestCase):
    def test_open_attendances_on_different_dates_allowed(self):
        emp = Employee.objects.create(
            first_name="Cara", last_name="Cole", email="att-day@example.com"
        )
        Attendance.objects.create(
            employee=emp,
            date=date(2026, 9, 10),
            clock_in=timezone.now(),
            clock_out=None,
        )
        Attendance.objects.create(
            employee=emp,
            date=date(2026, 9, 11),
            clock_in=timezone.now(),
            clock_out=None,
        )
        self.assertEqual(
            Attendance.objects.filter(employee=emp, clock_out__isnull=True).count(), 2
        )

    def test_duplicate_date_still_rejected(self):
        emp = Employee.objects.create(
            first_name="Dan", last_name="Diaz", email="att-dup@example.com"
        )
        Attendance.objects.create(employee=emp, date=date(2026, 9, 10))
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(employee=emp, date=date(2026, 9, 10))

    def test_second_slip_same_attendance_rejected_by_db(self):
        emp = Employee.objects.create(
            first_name="Eve", last_name="Ellis", email="att-ot@example.com"
        )
        att = Attendance.objects.create(employee=emp, date=date(2026, 9, 12))
        OvertimeSlip.objects.create(
            employee=emp,
            attendance=att,
            date=date(2026, 9, 12),
            hours=Decimal("1.00"),
        )
        with self.assertRaises(IntegrityError):
            OvertimeSlip.objects.create(
                employee=emp,
                attendance=att,
                date=date(2026, 9, 12),
                hours=Decimal("1.00"),
            )

    def test_per_day_open_constraint_definition(self):
        constraints = Attendance._meta.constraints
        match = [
            c
            for c in constraints
            if getattr(c, "name", "") == "one_open_attendance_per_employee_per_day"
        ]
        self.assertEqual(len(match), 1)
        self.assertEqual(tuple(match[0].fields), ("employee", "date"))
        self.assertEqual(match[0].condition, Q(clock_out__isnull=True))
        self.assertIn(("employee", "date"), Attendance._meta.unique_together)
