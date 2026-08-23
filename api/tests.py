from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient

# run "python manage.py test api.tests" to run these tests -- al

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
	def test_employee_create_forwards_payload_to_supabase(self, supabase):
		table = MagicMock()
		table.insert.return_value = table
		table.execute.return_value = SimpleNamespace(
			data=[{"email": "jane@example.com"}]
		)
		supabase.table.return_value = table
		payload = {
			"first_name": "Jane",
			"last_name": "Doe",
			"email": "jane@example.com",
		}

		response = self.client.post("/api/employees/", payload, format="json")

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.json(), [{"email": "jane@example.com"}])
		supabase.table.assert_called_once_with("employees")
		table.insert.assert_called_once_with(payload)

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
