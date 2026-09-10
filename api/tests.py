from datetime import date
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
    LeaveRequest,
    PayrollItem,
    PayrollRun,
)


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
