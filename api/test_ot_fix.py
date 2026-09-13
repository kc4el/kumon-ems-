"""Agent B: OT + leave_type serializer hardening (RED first)."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Attendance, Employee


class OvertimeSerializerFixTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(
            username="ot-fix-tester", password="x", is_staff=True
        )
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Over", last_name="Time", email="otfix@example.com"
        )
        self.other = Employee.objects.create(
            first_name="Oth", last_name="Er", email="otfix-other@example.com"
        )

    def _attendance(self, employee=None, day=None, worked_hours=9):
        employee = employee or self.employee
        if day is None:
            self._attn_days = getattr(self, "_attn_days", 1) + 1
            clock_in = timezone.now() - timedelta(days=self._attn_days)
        else:
            clock_in = timezone.make_aware(
                timezone.datetime.combine(day, timezone.datetime.min.time())
            ) + timedelta(hours=9)
        return Attendance.objects.create(
            employee=employee,
            date=clock_in.date(),
            clock_in=clock_in,
            clock_out=clock_in + timedelta(hours=worked_hours),
        )

    def _post_slip(self, attendance, **overrides):
        payload = {
            "employee": str(self.employee.id),
            "attendance": str(attendance.id),
            "date": str(attendance.date),
        }
        payload.update(overrides)
        return self.client.post("/api/overtime/", payload, format="json")

    def _slip_id(self, attendance=None):
        attendance = attendance or self._attendance()
        response = self._post_slip(attendance)
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_ot_status_invalid_choice_rejected_on_create(self):
        response = self._post_slip(self._attendance(), status="Bogus")
        self.assertEqual(response.status_code, 400)

    def test_ot_status_invalid_choice_rejected_on_update(self):
        slip_id = self._slip_id()
        response = self.client.patch(
            f"/api/overtime/{slip_id}/", {"status": "Bogus"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_ot_multiplier_below_min_rejected(self):
        response = self._post_slip(self._attendance(), multiplier="0.00")
        self.assertEqual(response.status_code, 400)

    def test_ot_multiplier_above_max_rejected(self):
        response = self._post_slip(self._attendance(), multiplier="5.01")
        self.assertEqual(response.status_code, 400)

    def test_ot_multiplier_boundaries_accepted(self):
        self.assertEqual(
            self._post_slip(self._attendance(), multiplier="0.01").status_code,
            201,
        )
        self.assertEqual(
            self._post_slip(self._attendance(), multiplier="5.00").status_code,
            201,
        )

    def test_ot_update_rejects_employee_change(self):
        slip_id = self._slip_id()
        response = self.client.patch(
            f"/api/overtime/{slip_id}/",
            {"employee": str(self.other.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_ot_update_rejects_attendance_change(self):
        slip_id = self._slip_id()
        newcomer = self._attendance()
        response = self.client.patch(
            f"/api/overtime/{slip_id}/",
            {"attendance": str(newcomer.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_ot_update_rejects_hours_change(self):
        slip_id = self._slip_id()
        response = self.client.patch(
            f"/api/overtime/{slip_id}/", {"hours": "99.00"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_ot_date_must_match_attendance_date(self):
        attendance = self._attendance()
        response = self._post_slip(attendance, date="2000-01-01")
        self.assertEqual(response.status_code, 400)

    def test_ot_employee_must_match_attendance_employee(self):
        attendance = self._attendance(employee=self.other)
        response = self._post_slip(attendance)
        self.assertEqual(response.status_code, 400)

    def test_ot_status_approve_still_works(self):
        slip_id = self._slip_id()
        response = self.client.patch(
            f"/api/overtime/{slip_id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Approved")


class LeaveTypeTitleCaseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(
            username="leave-fix-tester", password="x", is_staff=True
        )
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Lea", last_name="Ve", email="leavefix@example.com"
        )

    def _post_leave(self, **overrides):
        payload = {
            "employee": str(self.employee.id),
            "leave_type": "vacation",
            "start_date": str(date.today() + timedelta(days=1)),
            "end_date": str(date.today() + timedelta(days=2)),
            "reason": "rest",
        }
        payload.update(overrides)
        return self.client.post("/api/leaves/", payload, format="json")

    def test_leave_request_title_cases_lowercase(self):
        response = self._post_leave(leave_type="vacation")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["leave_type"], "Vacation")

    def test_leave_request_title_cases_shouty_padded(self):
        response = self._post_leave(leave_type="  VACATION ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["leave_type"], "Vacation")

    def test_leave_allocation_title_cases_type(self):
        for raw, want in (("sick", "Sick"), ("VACATION", "Vacation")):
            with self.subTest(raw=raw):
                response = self.client.post(
                    "/api/leave-allocations/",
                    {
                        "employee": str(self.employee.id),
                        "leave_type": raw,
                        "year": 2026,
                        "days_total": "5.0",
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["leave_type"], want)
