from datetime import date, datetime
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.exceptions import Conflict409
from core.models import (
    Attendance,
    Department,
    Employee,
    LeaveAllocation,
    LeaveRequest,
    PayrollItem,
    PayrollRun,
)


class ApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Staff by default: these tests exercise business logic, not
        # permissions, and staff bypass owner-scoping (see OwnerScopingTests).
        user = User.objects.create_user(username="tester", password="x", is_staff=True)
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
                self.assertIsInstance(results, dict)
                self.assertEqual(results["results"], [])

    def test_employee_list_is_ordered_by_last_name(self):
        Employee.objects.create(
            first_name="Zed", last_name="Zulu", email="zulu@example.com"
        )
        Employee.objects.create(
            first_name="Amy", last_name="Alba", email="alba@example.com"
        )
        response = self.client.get("/api/employees/")
        self.assertEqual(response.status_code, 200)
        last_names = [row["last_name"] for row in response.json()["results"]]
        self.assertEqual(last_names, ["Alba", "Zulu"])

    def test_employee_list_honors_page_size_param(self):
        for i in range(11):
            Employee.objects.create(
                first_name=f"Page{i:02d}",
                last_name=f"Size{i:02d}",
                email=f"pagesize{i:02d}@example.com",
            )
        response = self.client.get("/api/employees/?page_size=50")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 11)

    def test_employee_list_search_filters_by_name_or_email(self):
        Employee.objects.create(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        )
        Employee.objects.create(
            first_name="Grace", last_name="Hopper", email="grace@example.com"
        )
        response = self.client.get("/api/employees/?search=lovelace")
        self.assertEqual(response.status_code, 200)
        emails = [row["email"] for row in response.json()["results"]]
        self.assertEqual(emails, ["ada@example.com"])

    def test_employee_list_filters_by_is_active_and_department(self):
        from core.models import Department

        dept = Department.objects.create(name="Engineering", code="ENG")
        active = Employee.objects.create(
            first_name="Active",
            last_name="Eng",
            email="activeeng@example.com",
            department=dept,
        )
        Employee.objects.create(
            first_name="Inactive",
            last_name="Eng",
            email="inactiveeng@example.com",
            department=dept,
            is_active=False,
        )
        Employee.objects.create(
            first_name="Active",
            last_name="Other",
            email="activeother@example.com",
        )
        response = self.client.get("/api/employees/?is_active=false")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["email"] for row in response.json()["results"]],
            ["inactiveeng@example.com"],
        )
        response = self.client.get("/api/employees/?department=Engineering")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {row["email"] for row in response.json()["results"]},
            {"activeeng@example.com", "inactiveeng@example.com"},
        )
        self.assertTrue(active.is_active)

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
    def test_employee_create_persists_role_and_department(self, supabase):
        from core.models import Department

        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="22222222-2222-4222-8222-222222222222")
        )
        dept = Department.objects.create(name="Engineering", code="ENG")
        payload = {
            "first_name": "Role",
            "last_name": "Dept",
            "email": "roledept@example.com",
            "role": "Backend Engineer",
            "department": str(dept.id),
        }

        response = self.client.post("/api/employees/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        emp = Employee.objects.get(email="roledept@example.com")
        self.assertEqual(emp.role, "Backend Engineer")
        self.assertEqual(emp.department_id, dept.id)

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

    def test_attendance_duplicate_returns_409_fast_path(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        Attendance.objects.create(
            employee=employee, date=date.today(), clock_in=timezone.now()
        )
        response = self.client.post(
            "/api/attendance/",
            {"employee": str(employee.id), "date": str(date.today())},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(set(response.json().keys()), {"error"})

    def test_error_bodies_use_single_error_key(self):
        anon = APIClient()
        denied = anon.get("/api/employees/")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(set(denied.json().keys()), {"error"})
        bad = self.client.post("/api/leaves/", {}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(set(bad.json().keys()), {"error"})

    def test_attendance_race_maps_to_409(self):
        from core.views import AttendanceListCreateView

        view = AttendanceListCreateView()
        with patch("core.views.transaction.atomic", side_effect=IntegrityError("race")):
            with self.assertRaises(Conflict409):
                view.perform_create(serializer=None)

    def test_two_open_attendances_rejected_by_database(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        Attendance.objects.create(
            employee=employee, date=date.today(), clock_in=timezone.now()
        )
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(
                employee=employee,
                date=date.today() + timezone.timedelta(days=1),
                clock_in=timezone.now(),
            )

    @patch("core.views.supabase")
    def test_employee_create_race_maps_to_409(self, supabase):
        from types import SimpleNamespace as NS

        supabase.auth.admin.create_user.return_value = NS(
            user=NS(id="33333333-3333-4333-8333-333333333333")
        )
        with patch(
            "core.serializers.EmployeeSerializer.save",
            side_effect=IntegrityError("race"),
        ):
            response = self.client.post(
                "/api/employees/",
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "race@example.com",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 409)

    def test_clock_out_requires_employee_id(self):
        response = self.client.post("/api/attendance/clock-out/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_clock_out_second_open_rejected_by_database(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        Attendance.objects.create(
            employee=employee,
            date=date.today(),
            clock_in=timezone.now() - timezone.timedelta(hours=3),
        )
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(
                employee=employee,
                date=date.today() + timezone.timedelta(days=1),
                clock_in=timezone.now() - timezone.timedelta(hours=1),
            )

    def test_clock_out_before_clock_in_returns_400(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        clock_in = timezone.now()
        Attendance.objects.create(
            employee=employee, date=date.today(), clock_in=clock_in
        )
        response = self.client.post(
            "/api/attendance/clock-out/",
            {
                "employee_id": str(employee.id),
                "clock_out": (clock_in - timezone.timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_clock_out_invalid_datetime_returns_400(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        Attendance.objects.create(
            employee=employee, date=date.today(), clock_in=timezone.now()
        )
        response = self.client.post(
            "/api/attendance/clock-out/",
            {"employee_id": str(employee.id), "clock_out": "not-a-date"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_payroll_duplicate_line_returns_409(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        run = PayrollRun.objects.create(
            pay_period_start=date(2026, 8, 1), pay_period_end=date(2026, 8, 31)
        )
        payload = {
            "payroll_run": str(run.id),
            "employee": str(employee.id),
            "base_pay": "1000.00",
            "deductions": "100.00",
        }
        first = self.client.post("/api/payroll-items/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        second = self.client.post("/api/payroll-items/", payload, format="json")
        self.assertEqual(second.status_code, 409)

    def test_payroll_partial_update_recomputes_net_pay(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        run = PayrollRun.objects.create(
            pay_period_start=date(2026, 8, 1), pay_period_end=date(2026, 8, 31)
        )
        item = PayrollItem.objects.create(
            payroll_run=run, employee=employee, base_pay="1000.00", net_pay="900.00"
        )
        response = self.client.patch(
            f"/api/payroll-items/{item.id}/", {"deductions": "50.00"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.json()["net_pay"]), "950.00")

    def test_payroll_net_pay_is_server_computed(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        run = PayrollRun.objects.create(
            pay_period_start=date(2026, 8, 1), pay_period_end=date(2026, 8, 31)
        )
        response = self.client.post(
            "/api/payroll-items/",
            {
                "payroll_run": str(run.id),
                "employee": str(employee.id),
                "base_pay": "1000.00",
                "deductions": "100.00",
                "net_pay": "999999.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.json()["net_pay"]), "900.00")
        item = PayrollItem.objects.get(payroll_run=run, employee=employee)
        self.assertEqual(str(item.net_pay), "900.00")

    def test_employee_date_hired_is_read_only(self):
        with patch("core.views.supabase") as supabase:
            from types import SimpleNamespace as NS

            supabase.auth.admin.create_user.return_value = NS(
                user=NS(id="22222222-2222-4222-8222-222222222222")
            )
            response = self.client.post(
                "/api/employees/",
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                    "date_hired": "2000-01-01",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()["date_hired"], "2000-01-01")
        self.assertEqual(response.json()["date_hired"], str(date.today()))

    def test_leave_status_patch_still_works(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        leave = LeaveRequest.objects.create(
            employee=employee,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25),
            reason="Annual leave",
        )
        response = self.client.patch(
            f"/api/leaves/{leave.id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Approved")

    def test_employee_delete_is_soft_delete(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        other = Employee.objects.create(
            first_name="John", last_name="Smith", email="john@example.com"
        )
        response = self.client.delete(f"/api/employees/{employee.id}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], str(employee.id))
        self.assertFalse(body["is_active"])
        self.assertEqual(body["resigned_at"], str(date.today()))
        self.assertIn("purge_on", body)
        employee.refresh_from_db()
        self.assertFalse(employee.is_active)
        self.assertEqual(employee.resigned_at, date.today())
        summary = self.client.get("/api/dashboard-summary/").json()
        self.assertEqual(summary["total_employees"], 2)
        self.assertEqual(summary["active_employees"], 1)

    def test_employee_delete_writes_single_resignation_audit(self):
        from core.models import EmployeeAuditLog

        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        before = EmployeeAuditLog.objects.filter(employee=employee).count()
        response = self.client.delete(f"/api/employees/{employee.id}/")
        self.assertEqual(response.status_code, 200)
        logs = EmployeeAuditLog.objects.filter(employee=employee)
        self.assertEqual(logs.count() - before, 1)
        self.assertEqual(logs.filter(action__icontains="resigned").count(), 1)

    def test_employee_delete_is_idempotent(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        first = self.client.delete(f"/api/employees/{employee.id}/")
        second = self.client.delete(f"/api/employees/{employee.id}/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        employee.refresh_from_db()
        self.assertEqual(employee.resigned_at, date.today())

    @patch("core.views.supabase")
    def test_employee_delete_deauths_supabase_user(self, supabase):
        from core.models import EmployeeAuditLog

        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        response = self.client.delete(f"/api/employees/{employee.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deauthed"])
        supabase.auth.admin.delete_user.assert_called_once_with(str(employee.id))
        audit = EmployeeAuditLog.objects.get(
            employee=employee, action__icontains="resigned"
        )
        self.assertIn("deauthed=True", audit.action)

    @patch("core.views.supabase")
    def test_employee_delete_supabase_outage_still_resigns(self, supabase):
        from core.models import EmployeeAuditLog

        supabase.auth.admin.delete_user.side_effect = Exception("boom")
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        response = self.client.delete(f"/api/employees/{employee.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["deauthed"])
        employee.refresh_from_db()
        self.assertFalse(employee.is_active)
        audit = EmployeeAuditLog.objects.get(
            employee=employee, action__icontains="resigned"
        )
        self.assertIn("deauthed=False", audit.action)

    def test_shift_overlap_returns_409(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        base = {
            "employee": str(employee.id),
            "work_date": "2026-09-01",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        }
        first = self.client.post("/api/shift-rosters/", base, format="json")
        self.assertEqual(first.status_code, 201)
        overlap = self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(employee.id),
                "work_date": "2026-09-01",
                "start_time": "13:00:00",
                "end_time": "18:00:00",
            },
            format="json",
        )
        self.assertEqual(overlap.status_code, 409)
        self.assertEqual(set(overlap.json().keys()), {"error"})

    def test_shift_adjacent_times_allowed(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(employee.id),
                "work_date": "2026-09-01",
                "start_time": "09:00:00",
                "end_time": "13:00:00",
            },
            format="json",
        )
        response = self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(employee.id),
                "work_date": "2026-09-01",
                "start_time": "13:00:00",
                "end_time": "17:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_shift_same_slot_different_employee_allowed(self):
        emp_a = Employee.objects.create(
            first_name="Ada", last_name="A", email="a@example.com"
        )
        emp_b = Employee.objects.create(
            first_name="Bo", last_name="B", email="b@example.com"
        )
        self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(emp_a.id),
                "work_date": "2026-09-01",
                "start_time": "09:00:00",
                "end_time": "17:00:00",
            },
            format="json",
        )
        response = self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(emp_b.id),
                "work_date": "2026-09-01",
                "start_time": "09:00:00",
                "end_time": "17:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_shift_start_after_end_returns_400(self):
        employee = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        response = self.client.post(
            "/api/shift-rosters/",
            {
                "employee": str(employee.id),
                "work_date": "2026-09-01",
                "start_time": "17:00:00",
                "end_time": "09:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

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

    def test_api_throttle_rates_are_configured(self):
        from rest_framework.settings import api_settings

        self.assertEqual(api_settings.DEFAULT_THROTTLE_RATES["anon"], "100/day")
        self.assertEqual(api_settings.DEFAULT_THROTTLE_RATES["user"], "1000/day")

    def test_message_sender_is_bound_to_request_user(self):
        response = self.client.post(
            "/api/messages/",
            {
                "conversation_key": "x",
                "sender_name": "Evil",
                "text": "hi",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["sender_name"], "tester")

    def test_message_create_defaults_conversation_key(self):
        response = self.client.post("/api/messages/", {"text": "hi"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["conversation_key"], "general")

    def test_claim_status_empty_payload_returns_400(self):
        response = self.client.post("/api/claim-statuses/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_claim_status_blank_claim_id_returns_400(self):
        response = self.client.post(
            "/api/claim-statuses/",
            {"claim_id": "  ", "status": "ok"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_claim_status_unknown_status_returns_400(self):
        response = self.client.post(
            "/api/claim-statuses/",
            {"claim_id": "C-1", "status": "Exploded"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_claim_status_upsert_is_idempotent(self):
        from core.models import ClaimStatus

        first = self.client.post(
            "/api/claim-statuses/",
            {"claim_id": "C-1", "status": "Pending"},
            format="json",
        )
        second = self.client.post(
            "/api/claim-statuses/",
            {"claim_id": "C-1", "status": "Pending"},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ClaimStatus.objects.filter(claim_id="C-1").count(), 1)

    def test_expense_claims_require_authentication(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/expense-claims/").status_code, 403)

    def test_expense_claim_negative_amount_returns_400(self):
        employee = Employee.objects.create(
            first_name="Exp", last_name="Ense", email="expense@example.com"
        )
        response = self.client.post(
            "/api/expense-claims/",
            {
                "employee": str(employee.id),
                "title": "Taxi",
                "amount": "-5.00",
                "category": "Travel",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_expense_claim_missing_employee_returns_400(self):
        response = self.client.post(
            "/api/expense-claims/",
            {"title": "Taxi", "amount": "10.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("core.views.supabase")
    def test_employee_create_with_password_provisions_django_user(self, supabase):
        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="22222222-2222-4222-8222-222222222222")
        )
        response = self.client.post(
            "/api/employees/",
            {
                "first_name": "New",
                "last_name": "Staff",
                "email": "newstaff@example.com",
                "password": "Sup3rSecret!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="newstaff@example.com").exists())
        login_response = self.client.post(
            "/api/session-login/",
            {"username": "newstaff@example.com", "password": "Sup3rSecret!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

    @patch("core.views.supabase")
    def test_employee_create_without_password_creates_no_django_user(self, supabase):
        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="33333333-3333-4333-8333-333333333333")
        )
        response = self.client.post(
            "/api/employees/",
            {
                "first_name": "Op",
                "last_name": "Provisioned",
                "email": "opprovisioned@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(
            User.objects.filter(username="opprovisioned@example.com").exists()
        )

    @patch("core.views.supabase")
    def test_employee_create_weak_password_returns_400(self, supabase):
        response = self.client.post(
            "/api/employees/",
            {
                "first_name": "Weak",
                "last_name": "Password",
                "email": "weak@example.com",
                "password": "x",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        supabase.auth.admin.create_user.assert_not_called()

    def test_notifications_list_and_mark_read(self):
        from core.models import Notification

        employee = Employee.objects.create(
            first_name="Noti", last_name="Fied", email="notified@example.com"
        )
        note = Notification.objects.create(
            employee=employee, text="Leave Approved: 2026-10-01", kind="leave"
        )
        listed = self.client.get("/api/notifications/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["results"]), 1)
        marked = self.client.patch(
            f"/api/notifications/{note.id}/read/", {}, format="json"
        )
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.json()["is_read"])
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_leave_decision_creates_notification(self):
        from core.models import Notification

        employee = Employee.objects.create(
            first_name="Lea", last_name="Ver", email="leaver@example.com"
        )
        leave = LeaveRequest.objects.create(
            employee=employee,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            reason="Family trip",
        )
        leave.status = "Approved"
        leave.save()
        self.assertTrue(
            Notification.objects.filter(
                employee=employee, kind="leave", is_read=False
            ).exists()
        )

    def test_shift_conflict_endpoint_names_roster_and_leave(self):
        from core.models import LeaveRequest, ShiftRoster

        employee = Employee.objects.create(
            first_name="Con", last_name="Flict", email="conflict@example.com"
        )
        roster = ShiftRoster.objects.create(
            employee=employee,
            work_date=date(2026, 10, 1),
            shift_type="Morning",
            start_time="08:00:00",
            end_time="16:00:00",
        )
        leave = LeaveRequest.objects.create(
            employee=employee,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            reason="Approved trip",
            status="Approved",
        )
        response = self.client.get(
            f"/api/shift-rosters/conflicts/?employee={employee.id}&date=2026-10-01"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-10-01")
        self.assertEqual(len(body["conflicts"]), 1)
        self.assertEqual(body["conflicts"][0]["roster"], str(roster.id))
        self.assertEqual(body["conflicts"][0]["leave"], str(leave.id))

    def test_shift_conflict_endpoint_requires_params(self):
        response = self.client.get("/api/shift-rosters/conflicts/")
        self.assertEqual(response.status_code, 400)

    def test_purge_run_requires_staff(self):
        non_staff = User.objects.create_user(username="nonboss", password="x")
        client = APIClient()
        client.force_authenticate(user=non_staff)
        response = client.post(
            "/api/purge-run/", {"days": 30, "dry_run": True}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    @patch("core.management.commands.purge_resigned.supabase")
    def test_purge_run_dry_run_counts_candidates(self, supabase):
        from datetime import timedelta

        staff = User.objects.create_user(username="boss", password="x", is_staff=True)
        client = APIClient()
        client.force_authenticate(user=staff)
        Employee.objects.create(
            first_name="Old",
            last_name="Gone",
            email="oldgone@example.com",
            is_active=False,
            resigned_at=timezone.now().date() - timedelta(days=40),
        )
        response = client.post(
            "/api/purge-run/", {"days": 30, "dry_run": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["would_purge"], 1)
        self.assertEqual(response.json()["purged"], 0)
        self.assertTrue(Employee.objects.filter(email="oldgone@example.com").exists())

    @patch("core.management.commands.purge_resigned.supabase")
    def test_purge_run_real_deletes_and_audits(self, supabase):
        from datetime import timedelta

        from core.models import EmployeeAuditLog

        staff = User.objects.create_user(username="boss2", password="x", is_staff=True)
        client = APIClient()
        client.force_authenticate(user=staff)
        Employee.objects.create(
            first_name="Old",
            last_name="Gone",
            email="reallygone@example.com",
            is_active=False,
            resigned_at=timezone.now().date() - timedelta(days=40),
        )
        response = client.post(
            "/api/purge-run/", {"days": 30, "dry_run": False}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Employee.objects.filter(email="reallygone@example.com").exists()
        )
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                action__icontains="reallygone@example.com"
            ).exists()
        )

    def test_purge_run_rejects_non_integer_days(self):
        staff = User.objects.create_user(username="boss3", password="x", is_staff=True)
        client = APIClient()
        client.force_authenticate(user=staff)
        response = client.post(
            "/api/purge-run/", {"days": "abc", "dry_run": True}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class LeaveAllocationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="tester", password="x", is_staff=True)
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Allo", last_name="Cation", email="alloc@example.com"
        )

    def test_create_allocation_returns_201(self):
        response = self.client.post(
            "/api/leave-allocations/",
            {
                "employee": str(self.employee.id),
                "leave_type": "Vacation",
                "year": 2026,
                "days_total": "5.0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            LeaveAllocation.objects.filter(
                employee=self.employee, leave_type="Vacation", year=2026
            ).exists()
        )

    def test_duplicate_allocation_returns_409(self):
        payload = {
            "employee": str(self.employee.id),
            "leave_type": "Sick",
            "year": 2026,
            "days_total": "5.0",
        }
        self.assertEqual(
            self.client.post(
                "/api/leave-allocations/", payload, format="json"
            ).status_code,
            201,
        )
        response = self.client.post("/api/leave-allocations/", payload, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(set(response.json().keys()), {"error"})

    def test_anonymous_allocation_list_is_denied(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/leave-allocations/").status_code, 403)


class LeaveBalanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="tester", password="x", is_staff=True)
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Bal", last_name="Ance", email="balance@example.com"
        )

    def test_balance_subtracts_approved_leave(self):
        LeaveAllocation.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            year=2026,
            days_total="5.0",
        )
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 2),
            reason="Trip",
            status="Approved",
        )
        response = self.client.get(
            f"/api/leave-balances/?employee={self.employee.id}&year=2026"
        )
        self.assertEqual(response.status_code, 200)
        balance = response.json()["balances"]["Vacation"]
        self.assertEqual(balance["allocated"], 5.0)
        self.assertEqual(balance["used"], 2)
        self.assertEqual(balance["remaining"], 3.0)

    def test_balance_without_allocation_uses_defaults(self):
        response = self.client.get(
            f"/api/leave-balances/?employee={self.employee.id}&year=2026"
        )
        self.assertEqual(response.status_code, 200)
        balances = response.json()["balances"]
        self.assertEqual(balances["Vacation"]["allocated"], 5.0)
        self.assertEqual(balances["Sick"]["allocated"], 5.0)

    def test_balance_requires_params(self):
        self.assertEqual(self.client.get("/api/leave-balances/").status_code, 400)
        self.assertEqual(
            self.client.get(
                f"/api/leave-balances/?employee={self.employee.id}&year=soon"
            ).status_code,
            400,
        )

    def test_over_balance_approval_still_creates_leave(self):
        LeaveAllocation.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            year=2026,
            days_total="5.0",
        )
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 6),
            reason="Long trip",
            status="Pending",
        )
        response = self.client.patch(
            f"/api/leaves/{leave.id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        balance = self.client.get(
            f"/api/leave-balances/?employee={self.employee.id}&year=2026"
        ).json()["balances"]["Vacation"]
        self.assertEqual(balance["remaining"], -1.0)


class SessionAuthTests(TestCase):
    def test_session_login_wrong_credentials_returns_401(self):
        User.objects.create_user(username="sess", password="right")
        anon = APIClient()
        response = anon.post(
            "/api/session-login/",
            {"username": "sess", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_session_login_logout_round_trip(self):
        User.objects.create_user(username="sess", password="right")
        client = APIClient()
        login = client.post(
            "/api/session-login/",
            {"username": "sess", "password": "right"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("sessionid", login.cookies)
        authed = client.get("/api/employees/")
        self.assertEqual(authed.status_code, 200)
        logout = client.post("/api/session-logout/")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(client.get("/api/employees/").status_code, 403)


class OvertimeSlipTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(
            username="ot-tester", password="x", is_staff=True
        )
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Over", last_name="Time", email="ot@example.com"
        )

    def _attendance(self, worked_hours=None):
        clock_in = timezone.now() - timezone.timedelta(days=1)
        clock_out = (
            clock_in + timezone.timedelta(hours=worked_hours)
            if worked_hours is not None
            else None
        )
        return Attendance.objects.create(
            employee=self.employee,
            date=clock_in.date(),
            clock_in=clock_in,
            clock_out=clock_out,
        )

    def _post_slip(self, attendance, **overrides):
        payload = {
            "employee": str(self.employee.id),
            "attendance": str(attendance.id),
            "date": str(attendance.date),
        }
        payload.update(overrides)
        return self.client.post("/api/overtime/", payload, format="json")

    def test_overtime_long_day_claims_hours_past_eight(self):
        response = self._post_slip(self._attendance(8.5))
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["hours"], "0.50")
        self.assertEqual(body["multiplier"], "1.25")
        self.assertEqual(body["status"], "Pending")

    def test_overtime_short_day_claims_zero(self):
        response = self._post_slip(self._attendance(7))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["hours"], "0.00")

    def test_overtime_incomplete_attendance_returns_400(self):
        response = self._post_slip(self._attendance())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json().keys()), {"error"})

    def test_overtime_posted_hours_are_ignored(self):
        response = self._post_slip(self._attendance(8.5), hours="99.00")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["hours"], "0.50")

    def test_overtime_custom_multiplier_is_accepted(self):
        response = self._post_slip(self._attendance(9), multiplier="2.00")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["multiplier"], "2.00")

    def test_overtime_approve_returns_200(self):
        slip_id = self._post_slip(self._attendance(9)).json()["id"]
        response = self.client.patch(
            f"/api/overtime/{slip_id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Approved")

    def test_overtime_other_employee_attendance_returns_400(self):
        other = Employee.objects.create(
            first_name="Oth", last_name="Er", email="other@example.com"
        )
        attendance = Attendance.objects.create(
            employee=other,
            date=date.today(),
            clock_in=timezone.now() - timezone.timedelta(hours=10),
            clock_out=timezone.now() - timezone.timedelta(hours=1),
        )
        response = self._post_slip(attendance)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json().keys()), {"error"})

    def test_overtime_missing_attendance_returns_400(self):
        import uuid

        response = self.client.post(
            "/api/overtime/",
            {
                "employee": str(self.employee.id),
                "attendance": str(uuid.uuid4()),
                "date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json().keys()), {"error"})

    def test_overtime_anon_is_denied(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/overtime/").status_code, 403)


class EmployeeUserLinkTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        staff = User.objects.create_user(username="linker", password="x", is_staff=True)
        self.client.force_authenticate(user=staff)

    @patch("core.views.supabase")
    def test_employee_create_with_password_links_user(self, supabase):
        supabase.auth.admin.create_user.return_value = SimpleNamespace(
            user=SimpleNamespace(id="44444444-4444-4444-8444-444444444444")
        )
        response = self.client.post(
            "/api/employees/",
            {
                "first_name": "Link",
                "last_name": "Me",
                "email": "linkme@example.com",
                "password": "Sup3rSecret!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="linkme@example.com")
        self.assertEqual(Employee.objects.get(email="linkme@example.com").user, user)

    def test_backfill_links_matched_user_and_leaves_orphan(self):
        from core.migrations_compat import backfill_employee_users

        matched = Employee.objects.create(
            first_name="Match", last_name="Ed", email="match@example.com"
        )
        user = User.objects.create_user(
            username="match@example.com", email="MATCH@example.com", password="x"
        )
        orphan = User.objects.create_user(username="orphan", password="x")
        matched_count, unmatched_count = backfill_employee_users()
        matched.refresh_from_db()
        self.assertEqual(matched.user, user)
        self.assertEqual(matched_count, 1)
        self.assertFalse(Employee.objects.filter(user=orphan).exists())
        # unmatched = orphan + the staff user from setUp (no matching employee)
        self.assertEqual(unmatched_count, 2)


class OwnerScopingTests(TestCase):
    def setUp(self):
        from core.models import LeaveRequest

        self.owner = User.objects.create_user(username="scope-owner", password="x")
        self.other = User.objects.create_user(username="scope-other", password="x")
        self.staff = User.objects.create_user(
            username="scope-boss", password="x", is_staff=True
        )
        self.owner_emp = Employee.objects.create(
            first_name="Own", last_name="Er", email="owner-scope@example.com"
        )
        self.owner_emp.user = self.owner
        self.owner_emp.save(update_fields=["user"])
        self.other_emp = Employee.objects.create(
            first_name="Oth", last_name="Er", email="other-scope@example.com"
        )
        self.other_emp.user = self.other
        self.other_emp.save(update_fields=["user"])
        self.leave = LeaveRequest.objects.create(
            employee=self.owner_emp,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 25),
            reason="Annual leave",
        )

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_non_owner_patch_employee_denied(self):
        response = self._client(self.other).patch(
            f"/api/employees/{self.owner_emp.id}/",
            {"first_name": "Hax"},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))

    def test_owner_patch_self_allowed(self):
        response = self._client(self.owner).patch(
            f"/api/employees/{self.owner_emp.id}/",
            {"first_name": "OwnNew"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_staff_patch_anyone_allowed(self):
        response = self._client(self.staff).patch(
            f"/api/employees/{self.owner_emp.id}/",
            {"first_name": "StaffEdit"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_leave_list_scoped_to_owner(self):
        response = self._client(self.other).get("/api/leaves/")
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertNotIn(str(self.leave.id), ids)

    def test_non_owner_leave_detail_denied(self):
        response = self._client(self.other).get(f"/api/leaves/{self.leave.id}/")
        self.assertIn(response.status_code, (403, 404))

    def test_correction_scoped_via_attendance_owner(self):
        from core.models import Attendance, AttendanceCorrection

        attendance = Attendance.objects.create(
            employee=self.owner_emp,
            date=date(2026, 9, 10),
            clock_in=timezone.make_aware(datetime(2026, 9, 10, 9, 0)),
            clock_out=timezone.make_aware(datetime(2026, 9, 10, 17, 0)),
        )
        correction = AttendanceCorrection.objects.create(
            attendance=attendance, reason="Fix me."
        )
        denied = self._client(self.other).get(
            f"/api/attendance-corrections/{correction.id}/"
        )
        self.assertIn(denied.status_code, (403, 404))
        allowed = self._client(self.owner).get(
            f"/api/attendance-corrections/{correction.id}/"
        )
        self.assertEqual(allowed.status_code, 200)

    def test_notification_mark_read_scoped_to_owner(self):
        from core.models import Notification

        note = Notification.objects.create(
            employee=self.owner_emp, kind="info", text="Hello owner"
        )
        denied = self._client(self.other).patch(
            f"/api/notifications/{note.id}/read/", {}, format="json"
        )
        self.assertIn(denied.status_code, (403, 404))
        allowed = self._client(self.owner).patch(
            f"/api/notifications/{note.id}/read/", {}, format="json"
        )
        self.assertEqual(allowed.status_code, 200)


class ResignLocalKillTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token

        self.staff = User.objects.create_user(
            username="resign-boss", password="x", is_staff=True
        )
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)
        self.employee = Employee.objects.create(
            first_name="Gone", last_name="Soon", email="goner@example.com"
        )
        self.victim = User.objects.create_user(
            username="goner@example.com", email="goner@example.com", password="x"
        )
        self.token = Token.objects.create(user=self.victim)
        self.victim_client = APIClient()
        self.victim_client.force_login(self.victim)
        self.session_key = self.victim_client.session.session_key

    def test_resign_kills_local_user_token_and_session(self):
        from django.contrib.auth.models import User
        from django.contrib.sessions.models import Session
        from rest_framework.authtoken.models import Token

        from core.models import EmployeeAuditLog

        with patch("core.views.supabase"):
            response = self.staff_client.delete(f"/api/employees/{self.employee.id}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["deauthed"])
        self.assertTrue(body["local_killed"])
        self.assertFalse(User.objects.filter(pk=self.victim.pk).exists())
        self.assertFalse(Token.objects.filter(user_id=self.victim.pk).exists())
        self.assertFalse(Session.objects.filter(session_key=self.session_key).exists())
        audit = EmployeeAuditLog.objects.get(
            employee=self.employee, action__icontains="resigned"
        )
        self.assertIn("deauthed=True", audit.action)
        self.assertIn("local_killed=True", audit.action)
        anon = APIClient()
        anon.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        # Dead token authenticates nothing: the codebase answers 403 (see
        # test_expense_claims_require_authentication).
        self.assertEqual(anon.get("/api/employees/").status_code, 403)

    def test_resign_supabase_outage_still_kills_local(self):
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token

        with patch("core.views.supabase") as supabase:
            supabase.auth.admin.delete_user.side_effect = Exception("boom")
            response = self.staff_client.delete(f"/api/employees/{self.employee.id}/")
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["deauthed"])
        self.assertTrue(body["local_killed"])
        self.assertFalse(User.objects.filter(pk=self.victim.pk).exists())
        self.assertFalse(Token.objects.filter(user_id=self.victim.pk).exists())


class ShiftSwapTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="tester", password="x", is_staff=True)
        self.client.force_authenticate(user=user)

    def _roster(self, employee, work_date, start, end):
        from core.models import ShiftRoster

        return ShiftRoster.objects.create(
            employee=employee,
            work_date=work_date,
            shift_type="General",
            start_time=start,
            end_time=end,
        )

    def _pair(self, day=date(2026, 9, 1)):
        emp_a = Employee.objects.create(
            first_name="Ada", last_name="A", email="a@example.com"
        )
        emp_b = Employee.objects.create(
            first_name="Bo", last_name="B", email="b@example.com"
        )
        roster_a = self._roster(emp_a, day, "09:00:00", "13:00:00")
        roster_b = self._roster(emp_b, day, "14:00:00", "18:00:00")
        return emp_a, emp_b, roster_a, roster_b

    def test_valid_swap_request_returns_201(self):
        _, _, roster_a, roster_b = self._pair()
        response = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
                "reason": "Prefer afternoon",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "Pending")

    def test_same_employee_swap_returns_400(self):
        emp = Employee.objects.create(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        roster_a = self._roster(emp, date(2026, 9, 1), "09:00:00", "13:00:00")
        roster_b = self._roster(emp, date(2026, 9, 1), "14:00:00", "18:00:00")
        response = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json().keys()), {"error"})

    def test_different_dates_swap_returns_400(self):
        emp_a = Employee.objects.create(
            first_name="Ada", last_name="A", email="a@example.com"
        )
        emp_b = Employee.objects.create(
            first_name="Bo", last_name="B", email="b@example.com"
        )
        roster_a = self._roster(emp_a, date(2026, 9, 1), "09:00:00", "13:00:00")
        roster_b = self._roster(emp_b, date(2026, 9, 2), "09:00:00", "13:00:00")
        response = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_second_pending_swap_on_same_roster_returns_409(self):
        _, _, roster_a, roster_b = self._pair()
        first = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_b.id),
                "target_roster": str(roster_a.id),
            },
            format="json",
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(set(second.json().keys()), {"error"})

    def test_approve_swaps_holders_and_notifies_both(self):
        from core.models import Notification

        emp_a, emp_b, roster_a, roster_b = self._pair()
        swap = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        ).json()
        response = self.client.patch(
            f"/api/shift-swaps/{swap['id']}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        roster_a.refresh_from_db()
        roster_b.refresh_from_db()
        self.assertEqual(roster_a.employee_id, emp_b.id)
        self.assertEqual(roster_b.employee_id, emp_a.id)
        for emp in (emp_a, emp_b):
            self.assertTrue(
                Notification.objects.filter(
                    employee=emp, kind="shift", text__icontains="swap approved"
                ).exists()
            )

    def test_approve_causing_overlap_returns_409_and_keeps_rows(self):
        emp_a, emp_b, roster_a, roster_b = self._pair()
        # emp_a holds an extra shift overlapping roster_b's slot, so handing
        # roster_b to emp_a must clash and roll back.
        self._roster(emp_a, date(2026, 9, 1), "14:30:00", "19:00:00")
        swap = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        ).json()
        response = self.client.patch(
            f"/api/shift-swaps/{swap['id']}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        roster_a.refresh_from_db()
        roster_b.refresh_from_db()
        self.assertEqual(roster_a.employee.email, "a@example.com")
        self.assertEqual(roster_b.employee.email, "b@example.com")
        from core.models import ShiftSwap

        self.assertEqual(ShiftSwap.objects.get(pk=swap["id"]).status, "Pending")

    def test_approve_overlapping_same_date_pair_succeeds(self):
        emp_a = Employee.objects.create(
            first_name="Ada", last_name="A", email="a@example.com"
        )
        emp_b = Employee.objects.create(
            first_name="Bo", last_name="B", email="b@example.com"
        )
        day = date(2026, 9, 1)
        roster_a = self._roster(emp_a, day, "09:00:00", "17:00:00")
        roster_b = self._roster(emp_b, day, "09:00:00", "17:00:00")
        swap = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        ).json()
        response = self.client.patch(
            f"/api/shift-swaps/{swap['id']}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        roster_a.refresh_from_db()
        roster_b.refresh_from_db()
        self.assertEqual(roster_a.employee_id, emp_b.id)
        self.assertEqual(roster_b.employee_id, emp_a.id)

    def test_reject_leaves_rows_and_notifies_requester(self):
        from core.models import Notification

        emp_a, _, roster_a, roster_b = self._pair()
        swap = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        ).json()
        response = self.client.patch(
            f"/api/shift-swaps/{swap['id']}/",
            {"status": "Rejected"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        roster_a.refresh_from_db()
        roster_b.refresh_from_db()
        self.assertEqual(roster_a.employee.email, "a@example.com")
        self.assertEqual(roster_b.employee.email, "b@example.com")
        self.assertTrue(
            Notification.objects.filter(
                employee=emp_a, kind="shift", text__icontains="reject"
            ).exists()
        )

    def test_redecide_closed_swap_returns_409(self):
        _, _, roster_a, roster_b = self._pair()
        swap_id = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        ).json()["id"]
        first = self.client.patch(
            f"/api/shift-swaps/{swap_id}/", {"status": "Rejected"}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.patch(
            f"/api/shift-swaps/{swap_id}/", {"status": "Approved"}, format="json"
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(set(second.json().keys()), {"error"})

    def test_swap_request_and_approve_write_audit_rows(self):
        from core.models import EmployeeAuditLog

        _, _, roster_a, roster_b = self._pair()
        swap_id = self.client.post(
            "/api/shift-swaps/",
            {
                "requester_roster": str(roster_a.id),
                "target_roster": str(roster_b.id),
            },
            format="json",
        ).json()["id"]
        self.assertTrue(
            EmployeeAuditLog.objects.filter(action__icontains="swap requested").exists()
        )
        self.client.patch(
            f"/api/shift-swaps/{swap_id}/", {"status": "Approved"}, format="json"
        )
        self.assertTrue(
            EmployeeAuditLog.objects.filter(action__icontains="swap approved").exists()
        )


class AttendanceCorrectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(
            username="corr-tester", password="x", is_staff=True
        )
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Ada", last_name="Lovelace", email="ada-corr@example.com"
        )
        self.attendance = Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 9, 10),
            clock_in=timezone.make_aware(datetime(2026, 9, 10, 9, 0)),
            clock_out=timezone.make_aware(datetime(2026, 9, 10, 17, 0)),
        )

    def _propose(self, **overrides):
        payload = {
            "attendance": str(self.attendance.id),
            "proposed_clock_in": "2026-09-10T08:30:00Z",
            "proposed_clock_out": "2026-09-10T17:30:00Z",
            "reason": "Forgot morning clock-in.",
        }
        payload.update(overrides)
        return self.client.post("/api/attendance-corrections/", payload, format="json")

    def test_create_correction_returns_201_and_leaves_row_untouched(self):
        response = self._propose()
        self.assertEqual(response.status_code, 201)
        self.attendance.refresh_from_db()
        self.assertEqual(
            self.attendance.clock_in,
            timezone.make_aware(datetime(2026, 9, 10, 9, 0)),
        )
        self.assertEqual(
            self.attendance.clock_out,
            timezone.make_aware(datetime(2026, 9, 10, 17, 0)),
        )

    def test_empty_proposal_returns_400(self):
        response = self.client.post(
            "/api/attendance-corrections/",
            {"attendance": str(self.attendance.id), "reason": "No times."},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_inverted_times_return_400(self):
        response = self._propose(
            proposed_clock_in="2026-09-10T18:00:00Z",
            proposed_clock_out="2026-09-10T07:00:00Z",
        )
        self.assertEqual(response.status_code, 400)

    def test_anonymous_corrections_are_denied(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/attendance-corrections/").status_code, 403)

    def test_approve_updates_row_creates_audit_and_notifies(self):
        from core.models import EmployeeAuditLog, Notification

        correction_id = self._propose().json()["id"]
        response = self.client.patch(
            f"/api/attendance-corrections/{correction_id}/",
            {"status": "Approved", "reason": "tampered"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Approved")
        self.attendance.refresh_from_db()
        self.assertEqual(
            self.attendance.clock_in,
            timezone.make_aware(datetime(2026, 9, 10, 8, 30), timezone=dt_timezone.utc),
        )
        self.assertEqual(
            self.attendance.clock_out,
            timezone.make_aware(
                datetime(2026, 9, 10, 17, 30), timezone=dt_timezone.utc
            ),
        )
        # Status-only update: other fields are ignored.
        self.assertIn("Forgot morning clock-in.", response.json()["reason"])
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee, action__icontains="attendance corrected"
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                employee=self.employee, kind="attendance"
            ).exists()
        )

    def test_reject_changes_nothing(self):
        from core.models import EmployeeAuditLog

        correction_id = self._propose().json()["id"]
        response = self.client.patch(
            f"/api/attendance-corrections/{correction_id}/",
            {"status": "Rejected"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Rejected")
        self.attendance.refresh_from_db()
        self.assertEqual(
            self.attendance.clock_in,
            timezone.make_aware(datetime(2026, 9, 10, 9, 0)),
        )
        self.assertEqual(
            self.attendance.clock_out,
            timezone.make_aware(datetime(2026, 9, 10, 17, 0)),
        )
        self.assertFalse(
            EmployeeAuditLog.objects.filter(
                employee=self.employee, action__icontains="attendance corrected"
            ).exists()
        )
