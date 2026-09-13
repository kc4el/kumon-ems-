from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

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
