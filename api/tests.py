from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Attendance, Department, Employee, LeaveRequest


class ApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

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
            LeaveRequest.objects.filter(employee=employee, reason="Annual leave").exists()
        )
