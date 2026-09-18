"""Agent A red tests: T1 inactive gate, T2 FK-first resign kill, T4 decided-409.

Run: DB_HOST= ./.venv/Scripts/python manage.py test api.test_auth_fix
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from core.models import Attendance, Employee, ExpenseClaim, LeaveRequest

DECIDED_BODY = {"error": "This request has already been decided."}


class T1InactiveGateTests(APITestCase):
    def test_inactive_employee_nonstaff_blocked_at_detail(self):
        user = User.objects.create_user(username="inactive-emp", password="x")
        emp = Employee.objects.create(
            first_name="In",
            last_name="Active",
            email="inactive-emp@example.com",
            user=user,
            is_active=False,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f"/api/employees/{emp.id}/")
        self.assertEqual(response.status_code, 403)

    def test_inactive_django_user_nonstaff_blocked(self):
        user = User.objects.create_user(
            username="dead-user", password="x", is_active=False
        )
        emp = Employee.objects.create(
            first_name="Dead",
            last_name="User",
            email="dead-user@example.com",
            user=user,
            is_active=True,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f"/api/employees/{emp.id}/")
        self.assertEqual(response.status_code, 403)

    def test_staff_bypass_inactive_gate(self):
        staff = User.objects.create_user(
            username="boss-bypass", password="x", is_staff=True
        )
        emp = Employee.objects.create(
            first_name="Gone",
            last_name="Staff",
            email="gone-staff@example.com",
            is_active=False,
        )
        client = APIClient()
        client.force_authenticate(user=staff)
        response = client.get(f"/api/employees/{emp.id}/")
        self.assertEqual(response.status_code, 200)

    def test_session_login_generic_401(self):
        User.objects.create_user(username="sess-t1", password="right")
        anon = APIClient()
        bad = anon.post(
            "/api/session-login/",
            {"username": "sess-t1", "password": "wrong"},
            format="json",
        )
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(bad.json(), {"error": "Invalid credentials."})
        unknown = anon.post(
            "/api/session-login/",
            {"username": "no-such-user", "password": "wrong"},
            format="json",
        )
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(unknown.json(), {"error": "Invalid credentials."})


class T2ResignFkFirstTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="resign-boss-a", password="x", is_staff=True
        )
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)

    def test_resign_kills_fk_linked_user_with_different_email(self):
        victim = User.objects.create_user(
            username="fk-victim", email="other@example.com", password="x"
        )
        emp = Employee.objects.create(
            first_name="Fk",
            last_name="Linked",
            email="emp-fk@example.com",
            user=victim,
        )
        with patch("core.views.supabase"):
            response = self.staff_client.delete(f"/api/employees/{emp.id}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["local_killed"])
        self.assertFalse(User.objects.filter(pk=victim.pk).exists())

    def test_resign_email_fallback_still_kills(self):
        victim = User.objects.create_user(
            username="goner-fk@example.com",
            email="goner-fk@example.com",
            password="x",
        )
        emp = Employee.objects.create(
            first_name="Gone",
            last_name="Fallback",
            email="goner-fk@example.com",
        )
        with patch("core.views.supabase"):
            response = self.staff_client.delete(f"/api/employees/{emp.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["local_killed"])
        self.assertFalse(User.objects.filter(pk=victim.pk).exists())

    def test_resign_response_keys(self):
        emp = Employee.objects.create(
            first_name="Key", last_name="Check", email="keycheck@example.com"
        )
        with patch("core.views.supabase"):
            response = self.staff_client.delete(f"/api/employees/{emp.id}/")
        body = response.json()
        for key in (
            "id",
            "is_active",
            "resigned_at",
            "purge_on",
            "deauthed",
            "local_killed",
        ):
            self.assertIn(key, body)


class T4DecidedGuardTests(APITestCase):
    def setUp(self):
        staff = User.objects.create_user(
            username="decider-a", password="x", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(user=staff)
        self.employee = Employee.objects.create(
            first_name="Dec", last_name="Ide", email="decide-a@example.com"
        )

    def test_leave_redecide_409(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25),
            reason="Annual leave",
        )
        first = self.client.patch(
            f"/api/leaves/{leave.id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.patch(
            f"/api/leaves/{leave.id}/", {"status": "Rejected"}, format="json"
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json(), DECIDED_BODY)

    def test_leave_put_redecide_409(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25),
            reason="Annual leave",
            status="Rejected",
        )
        response = self.client.put(
            f"/api/leaves/{leave.id}/",
            {
                "employee": str(self.employee.id),
                "leave_type": leave.leave_type,
                "start_date": "2026-08-24",
                "end_date": "2026-08-25",
                "reason": "Annual leave",
                "status": "Approved",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), DECIDED_BODY)

    def test_expense_redecide_409(self):
        claim = ExpenseClaim.objects.create(
            employee=self.employee, title="Taxi", amount="10.00"
        )
        first = self.client.patch(
            f"/api/expense-claims/{claim.id}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.patch(
            f"/api/expense-claims/{claim.id}/",
            {"status": "Rejected"},
            format="json",
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json(), DECIDED_BODY)

    def test_ot_redecide_409(self):
        now = timezone.now()
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=now.date(),
            clock_in=now - timezone.timedelta(hours=10),
            clock_out=now - timezone.timedelta(hours=1),
        )
        slip_id = self.client.post(
            "/api/overtime/",
            {
                "employee": str(self.employee.id),
                "attendance": str(attendance.id),
                "date": str(attendance.date),
            },
            format="json",
        ).json()["id"]
        first = self.client.patch(
            f"/api/overtime/{slip_id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.patch(
            f"/api/overtime/{slip_id}/", {"status": "Rejected"}, format="json"
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json(), DECIDED_BODY)

    def test_pending_decision_still_200_and_same_status_idempotent(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25),
            reason="Annual leave",
        )
        first = self.client.patch(
            f"/api/leaves/{leave.id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        same = self.client.patch(
            f"/api/leaves/{leave.id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(same.status_code, 200)
        self.assertEqual(same.json()["status"], "Approved")
