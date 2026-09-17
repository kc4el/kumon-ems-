"""T2-T6: FrappeHR-mirror enforcement (own file)."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Employee, LeaveAllocation, LeaveRequest, SiteSetting


def _staff_client(username="frappe-enf"):
    client = APIClient()
    user = User.objects.create_user(username=username, password="x", is_staff=True)
    client.force_authenticate(user=user)
    return client


class DoubleBookingTests(TestCase):
    def setUp(self):
        self.client = _staff_client()
        self.emp = Employee.objects.create(
            first_name="D", last_name="B", email="db@example.com"
        )
        self.base = {
            "employee": str(self.emp.id),
            "work_date": "2026-10-01",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        }

    def _overlap(self):
        return self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(self.emp.id),
                "work_date": "2026-10-01",
                "start_time": "13:00:00",
                "end_time": "18:00:00",
            },
            format="json",
        )

    def test_default_still_409(self):
        self.assertEqual(
            self.client.post("/api/shift-rosters/", self.base, format="json").status_code,
            201,
        )
        self.assertEqual(self._overlap().status_code, 409)

    def test_toggle_on_allows_double_booking(self):
        SiteSetting.objects.update_or_create(
            key="shift_allow_double_booking", defaults={"value": "true"}
        )
        self.assertEqual(
            self.client.post("/api/shift-rosters/", self.base, format="json").status_code,
            201,
        )
        self.assertEqual(self._overlap().status_code, 201)


class BackdatedLeaveTests(TestCase):
    def setUp(self):
        self.client = _staff_client("frappe-leave")
        self.emp = Employee.objects.create(
            first_name="B", last_name="L", email="bl@example.com"
        )

    def _file(self, start):
        return self.client.post(
            "/api/leaves/",
            {
                "employee": str(self.emp.id),
                "leave_type": "Vacation",
                "start_date": str(start),
                "end_date": str(start + timedelta(days=1)),
                "reason": "x",
            },
            format="json",
        )

    def test_default_allows_backdated(self):
        past = date.today() - timedelta(days=30)
        self.assertEqual(self._file(past).status_code, 201)

    def test_toggle_on_rejects_backdated(self):
        SiteSetting.objects.update_or_create(
            key="leave_restrict_backdated", defaults={"value": "true"}
        )
        r = self._file(date.today() - timedelta(days=30))
        self.assertEqual(r.status_code, 400)
        self.assertIn("Backdated", r.text)
        self.assertEqual(self._file(date.today()).status_code, 201)


class AutoAllocateTests(TestCase):
    def test_default_hire_creates_nothing(self):
        Employee.objects.create(first_name="N", last_name="A", email="na@example.com")
        self.assertEqual(LeaveAllocation.objects.count(), 0)

    def test_toggle_on_allocates_vacation(self):
        SiteSetting.objects.update_or_create(
            key="leave_auto_allocate_days", defaults={"value": "14"}
        )
        emp = Employee.objects.create(
            first_name="A", last_name="B", email="ab@example.com"
        )
        row = LeaveAllocation.objects.get(
            employee=emp, leave_type="Vacation", year=date.today().year
        )
        self.assertEqual(float(row.days_total), 14)
        emp.first_name = "A2"
        emp.save()
        self.assertEqual(
            LeaveAllocation.objects.filter(employee=emp).count(), 1
        )


class MobileCheckinToggleTests(TestCase):
    def test_kiosk_default_path_unchanged(self):
        r = APIClient().post("/api/attendance/check-in/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_kiosk_disabled_returns_403(self):
        SiteSetting.objects.update_or_create(
            key="mobile_checkin_enabled", defaults={"value": "false"}
        )
        r = APIClient().post("/api/attendance/check-in/", {}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("disabled", r.json()["error"])

    def test_self_post_disabled_returns_403(self):
        from django.contrib.auth.models import User as U

        user = U.objects.create_user(username="mob", password="x")
        Employee.objects.create(
            first_name="M", last_name="O", email="mo@example.com", user=user
        )
        client = APIClient()
        client.force_authenticate(user=user)
        SiteSetting.objects.update_or_create(
            key="mobile_checkin_enabled", defaults={"value": "false"}
        )
        r = client.post(
            "/api/attendance/me/", {"action": "clock_in"}, format="json"
        )
        self.assertEqual(r.status_code, 403)
