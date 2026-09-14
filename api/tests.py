from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient


class SupabaseApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("core.views.supabase")
    def test_list_endpoints_use_existing_supabase_tables(self, supabase):
        table = MagicMock()
        table.select.return_value = table
        table.execute.return_value = SimpleNamespace(data=[])
        supabase.table.return_value = table

        endpoints = {
            "/api/departments/": "departments",
            "/api/employees/": "employees",
            "/api/attendance/": "attendance",
            "/api/leaves/": "leave_requests",
            "/api/shift-rosters/": "shift_rosters",
            "/api/payroll-runs/": "payroll_runs",
            "/api/payroll-items/": "payroll_items",
            "/api/performance/": "core_performancereview",
            "/api/audit-logs/": "employee_audit_logs",
        }

        for endpoint, table_name in endpoints.items():
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), [])
                supabase.table.assert_called_with(table_name)

    @patch("core.views.supabase")
    def test_dashboard_summary_aggregates_live_records(self, supabase):
        employees = MagicMock()
        employees.select.return_value = employees
        employees.execute.return_value = SimpleNamespace(
            data=[{"id": "1", "is_active": True}, {"id": "2", "is_active": False}]
        )
        leaves = MagicMock()
        leaves.select.return_value = leaves
        leaves.execute.return_value = SimpleNamespace(
            data=[{"id": "1", "status": "Approved"}, {"id": "2", "status": "Pending"}]
        )
        attendance = MagicMock()
        attendance.select.return_value = attendance
        attendance.execute.return_value = SimpleNamespace(
            data=[
                {"id": "1", "clock_out": None},
                {"id": "2", "clock_out": "2026-08-25T17:00:00Z"},
            ]
        )
        supabase.table.side_effect = {
            "employees": employees,
            "leave_requests": leaves,
            "attendance": attendance,
        }.get

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
    def test_employee_create_forwards_payload_to_supabase(self, supabase):
        table = MagicMock()
        table.insert.return_value = table
        table.execute.return_value = SimpleNamespace(data=[{"email": "jane@example.com"}])
        supabase.table.return_value = table
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
        self.assertEqual(response.json(), [{"email": "jane@example.com"}])
        supabase.auth.admin.create_user.assert_called_once()
        supabase.table.assert_called_once_with("employees")
        inserted_payload = table.insert.call_args.args[0]
        self.assertEqual({key: inserted_payload[key] for key in payload}, payload)
        self.assertIn("id", inserted_payload)
        self.assertTrue(inserted_payload["employee_code"].startswith("EMP-"))

    @patch("core.views.supabase")
    def test_leave_create_uses_leave_requests_table(self, supabase):
        table = MagicMock()
        table.insert.return_value = table
        table.execute.return_value = SimpleNamespace(data=[{"status": "Pending"}])
        supabase.table.return_value = table
        payload = {
            "employee_id": "employee-id",
            "start_date": "2026-08-24",
            "end_date": "2026-08-25",
            "reason": "Annual leave",
        }

        response = self.client.post("/api/leaves/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), [{"status": "Pending"}])
        supabase.table.assert_called_once_with("leave_requests")
        table.insert.assert_called_once_with(payload)
