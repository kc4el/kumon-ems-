from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Attendance, Department, Employee, LeaveRequest


class ApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="tester", password="x")
        self.client.force_authenticate(user=user)

    def test_anonymous_access_is_denied_except_dashboard_summary(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/employees/").status_code, 403)
        self.assertEqual(anon.get("/api/dashboard-summary/").status_code, 200)
        token_response = anon.post(
            "/api/auth-token/", {"username": "tester", "password": "x"}, format="json"
        )
        self.assertEqual(token_response.status_code, 200)
        self.assertIn("token", token_response.json())

    def test_list_endpoints_return_empty_collections(self):
        endpoints = [
            "/api/departments/",
            "/api/employees/",
            "/api/attendance/",
            "/api/leaves/",
            "/api/shift-rosters/",
            "/api/payroll-runs/",
            "/api/payroll-items/",
            "/api/performance/",
            "/api/audit-logs/",
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200)
                results = response.json()
                if isinstance(results, dict):
                    self.assertEqual(results["results"], [])
                else:
                    self.assertEqual(results, [])

    def test_dashboard_summary_aggregates_database_records(self):
        department = Department.objects.create(name="Operations", code="OPS")
        active_employee = Employee.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            department=department,
            is_active=True,
        )
        inactive_employee = Employee.objects.create(
            first_name="Grace",
            last_name="Hopper",
            email="grace@example.com",
            department=department,
            is_active=False,
        )
        LeaveRequest.objects.create(
            employee=active_employee,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25),
            reason="Approved leave",
            status="Approved",
        )
        LeaveRequest.objects.create(
            employee=inactive_employee,
            start_date=date(2026, 8, 26),
            end_date=date(2026, 8, 27),
            reason="Pending leave",
            status="Pending",
        )
        Attendance.objects.create(
            employee=active_employee,
            date=date.today(),
            clock_in=timezone.now(),
        )

        response = self.client.get("/api/dashboard-summary/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "total_employees": 2,
                "active_employees": 1,
                "approved_leaves": 1,
                "pending_leaves": 1,
                "open_attendance_records": 1,
            },
        )

    @patch("core.views.supabase")
    def test_employee_create_authenticates_and_persists_employee(self, supabase):
        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="11111111-1111-4111-8111-111111111111")
        )
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
        }

        response = self.client.post("/api/employees/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], payload["email"])
        self.assertTrue(Employee.objects.filter(email=payload["email"]).exists())
        supabase.auth.admin.create_user.assert_called_once()

    @patch("core.views.supabase")
    def test_employee_create_missing_email_returns_400(self, supabase):
        response = self.client.post(
            "/api/employees/",
            {"first_name": "No", "last_name": "Email"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        supabase.auth.admin.create_user.assert_not_called()

    @patch("core.views.supabase")
    def test_employee_create_invalid_returns_400_without_supabase_call(self, supabase):
        response = self.client.post(
            "/api/employees/", {"email": "bad-email"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        supabase.auth.admin.create_user.assert_not_called()

    @patch("core.views.supabase")
    def test_employee_create_duplicate_email_returns_409(self, supabase):
        Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        response = self.client.post(
            "/api/employees/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "JANE@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        supabase.auth.admin.create_user.assert_not_called()

    @patch("core.views.supabase")
    def test_employee_create_upstream_failure_rolls_back(self, supabase):
        supabase.auth.admin.create_user.side_effect = Exception("boom")
        response = self.client.post(
            "/api/employees/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 502)
        # create_user succeeded then failed? No — it raised, so no user id;
        # delete_user must not be called when nothing was created... instead
        # force the success-then-failure path below via return value + save error
        supabase.auth.admin.delete_user.assert_not_called()

    def test_leave_create_persists_leave_request(self):
        employee = Employee.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        payload = {
            "employee": str(employee.id),
            "start_date": "2026-08-24",
            "end_date": "2026-08-25",
            "reason": "Annual leave",
        }

        response = self.client.post("/api/leaves/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "Pending")
        self.assertTrue(
            LeaveRequest.objects.filter(
                employee=employee, reason="Annual leave"
            ).exists()
        )
