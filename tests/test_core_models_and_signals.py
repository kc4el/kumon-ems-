from datetime import date, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.utils import timezone

from core.models import (
    Attendance,
    Department,
    Employee,
    EmployeeAuditLog,
    LeaveAllocation,
    LeaveRequest,
    Notification,
    OvertimeSlip,
)


class AuditLogTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Operations", code="OPS")
        self.employee = Employee.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            department=self.department,
        )

    def test_employee_creation_logs_an_audit_entry(self):
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains="created",
            ).exists()
        )

    def test_attendance_clock_in_and_clock_out_create_audit_entries(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=date.today(),
            clock_in=timezone.now(),
        )

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains="Clocked IN",
            ).exists()
        )

        attendance.clock_out = timezone.now()
        attendance.save()

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains="Clocked OUT",
            ).exists()
        )

    def test_leave_status_updates_are_logged(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="Annual",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            reason="Family leave",
            status="Pending",
        )

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains="Submitted leave request",
            ).exists()
        )

        leave.status = "Approved"
        leave.save()

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains="Approved",
            ).exists()
        )


class LeaveDeficitTests(TestCase):
    def setUp(self):
        self.employee = Employee.objects.create(
            first_name="Defi", last_name="Cit", email="deficit@example.com"
        )
        LeaveAllocation.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            year=2026,
            days_total="5.0",
        )

    def test_approval_into_negative_sends_single_deficit_notice(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 6),
            reason="Long trip",
            status="Pending",
        )
        leave.status = "Approved"
        leave.save()
        deficit = Notification.objects.filter(
            employee=self.employee, kind="leave", text__icontains="over balance"
        )
        self.assertEqual(deficit.count(), 1)

    def test_approval_within_balance_sends_no_deficit_text(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="Vacation",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
            reason="Short trip",
            status="Pending",
        )
        leave.status = "Approved"
        leave.save()
        self.assertFalse(
            Notification.objects.filter(
                employee=self.employee, text__icontains="over balance"
            ).exists()
        )


class PaginationOrderingTests(TestCase):
    def test_paginated_views_use_stable_ordering(self):
        from .views import (
            EmployeeListCreateView,
            PayrollItemListCreateView,
            PayrollRunListCreateView,
            PerformanceReviewListCreateView,
            ShiftRosterListCreateView,
        )

        self.assertEqual(
            EmployeeListCreateView.queryset.query.order_by,
            ("last_name", "first_name"),
        )
        self.assertEqual(
            ShiftRosterListCreateView.queryset.query.order_by,
            ("work_date", "start_time"),
        )
        self.assertEqual(
            PayrollRunListCreateView.queryset.query.order_by,
            ("-pay_period_start",),
        )
        self.assertEqual(
            PayrollItemListCreateView.queryset.query.order_by,
            ("payroll_run__pay_period_start", "employee__last_name"),
        )
        self.assertEqual(
            PerformanceReviewListCreateView.queryset.query.order_by,
            ("-review_date",),
        )


class PurgeResignedTests(TestCase):
    @patch("core.management.commands.purge_resigned.supabase")
    def test_purge_removes_only_old_resignations(self, supabase):
        from io import StringIO

        old = Employee.objects.create(
            first_name="Old",
            last_name="Gone",
            email="old@example.com",
            is_active=False,
            resigned_at=date.today() - timedelta(days=31),
        )
        recent = Employee.objects.create(
            first_name="New",
            last_name="Kept",
            email="recent@example.com",
            is_active=False,
            resigned_at=date.today() - timedelta(days=10),
        )
        out = StringIO()
        call_command("purge_resigned", stdout=out)
        self.assertFalse(Employee.objects.filter(pk=old.pk).exists())
        self.assertTrue(Employee.objects.filter(pk=recent.pk).exists())
        supabase.auth.admin.delete_user.assert_called_once_with(str(old.id))

    @patch("core.management.commands.purge_resigned.supabase")
    def test_purge_dry_run_keeps_everyone(self, supabase):
        from io import StringIO

        old = Employee.objects.create(
            first_name="Old",
            last_name="Gone",
            email="old@example.com",
            is_active=False,
            resigned_at=date.today() - timedelta(days=31),
        )
        out = StringIO()
        call_command("purge_resigned", "--dry-run", stdout=out)
        self.assertTrue(Employee.objects.filter(pk=old.pk).exists())
        supabase.auth.admin.delete_user.assert_not_called()
        self.assertIn("would purge", out.getvalue())

    @patch("core.management.commands.purge_resigned.supabase")
    def test_purge_failure_keeps_row(self, supabase):
        from io import StringIO

        supabase.auth.admin.delete_user.side_effect = Exception("boom")
        old = Employee.objects.create(
            first_name="Old",
            last_name="Gone",
            email="failkeep@example.com",
            is_active=False,
            resigned_at=date.today() - timedelta(days=31),
        )
        call_command("purge_resigned", stdout=StringIO())
        self.assertTrue(Employee.objects.filter(pk=old.pk).exists())

    def test_purge_negative_days_rejected(self):
        from io import StringIO

        with self.assertRaises(CommandError):
            call_command("purge_resigned", "--days", "-5", stdout=StringIO())

    @patch("core.management.commands.purge_resigned.supabase")
    def test_purge_success_writes_audit(self, supabase):
        from io import StringIO

        old = Employee.objects.create(
            first_name="Old",
            last_name="Audit",
            email="auditme@example.com",
            is_active=False,
            resigned_at=date.today() - timedelta(days=31),
        )
        call_command("purge_resigned", stdout=StringIO())
        self.assertFalse(Employee.objects.filter(pk=old.pk).exists())
        self.assertEqual(
            EmployeeAuditLog.objects.filter(action__icontains="purged").count(), 1
        )


class PageViewTests(TestCase):
    def test_dashboard_view_renders_successfully(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kumon EMS")
        self.assertContains(response, "view-dashboard")

    def test_login_view_renders_successfully(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign In to Portal")
        self.assertContains(response, "Complete Registration")

    def test_hr_login_and_dashboard_are_separate(self):
        response = self.client.get("/hr/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HR dashboard sign in")

        anonymous_dashboard = self.client.get("/hr/")
        self.assertEqual(anonymous_dashboard.status_code, 302)
        self.assertIn("/hr/login/", anonymous_dashboard["Location"])

    def test_hr_session_login_requires_staff(self):
        employee = User.objects.create_user(username="employee", password="pw")
        hr = User.objects.create_user(username="hr", password="pw", is_staff=True)
        client = APIClient()

        denied = client.post(
            "/api/hr-session-login/",
            {"username": employee.username, "password": "pw"},
            format="json",
        )
        self.assertEqual(denied.status_code, 401)

        allowed = client.post(
            "/api/hr-session-login/",
            {"username": hr.username, "password": "pw"},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["next_url"], "/hr/")

        dashboard = client.get("/hr/")
        self.assertEqual(dashboard.status_code, 200)

    def test_hr_login_by_email_keeps_session_for_dashboard(self):
        hr = User.objects.create_user(
            username="hr-user", email="hr-user@example.com", password="pw", is_staff=True
        )
        client = Client()
        response = client.post(
            "/api/hr-session-login/",
            {"username": "hr-user@example.com", "password": "pw"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["next_url"], "/hr/")
        self.assertIn("sessionid", client.cookies)
        dashboard = client.get("/hr/")
        self.assertEqual(dashboard.status_code, 200)

    def test_role_landing_pages_do_not_cross_redirect(self):
        staff = User.objects.create_user(username="role-hr", password="pw", is_staff=True)
        employee_user = User.objects.create_user(username="role-employee", password="pw")
        Employee.objects.create(
            first_name="Role",
            last_name="Employee",
            email="role-employee@example.com",
            user=employee_user,
        )

        staff_client = self.client
        staff_client.force_login(staff)
        self.assertEqual(staff_client.get("/").url, "/hr/")
        self.assertEqual(staff_client.get("/employee/").url, "/hr/")

        employee_client = Client()
        employee_client.force_login(employee_user)
        self.assertEqual(employee_client.get("/").url, "/employee/")
        self.assertEqual(employee_client.get("/hr/").url, "/hr/login/?next=/hr/")

    def test_root_uses_hr_role_for_hr_linked_nonstaff(self):
        hr_user = User.objects.create_user(username="linked-hr", password="pw")
        hr_department = Department.objects.create(name="HR", code="HR-ROLE")
        Employee.objects.create(
            first_name="Linked",
            last_name="HR",
            email="linked-hr@example.com",
            department=hr_department,
            user=hr_user,
        )
        self.client.force_login(hr_user)
        self.assertEqual(self.client.get("/").url, "/hr/")
        self.assertEqual(self.client.get("/employee/").status_code, 200)

    def test_employee_login_rejects_hr_account_without_session(self):
        hr_user = User.objects.create_user(username="hr-through-employee", password="pw")
        hr_department = Department.objects.create(name="HR", code="HR-LOGIN")
        Employee.objects.create(
            first_name="HR",
            last_name="Login",
            email="hr-through-employee@example.com",
            department=hr_department,
            user=hr_user,
        )
        client = Client()
        response = client.post(
            "/api/session-login/",
            {"username": hr_user.username, "password": "pw"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("sessionid", client.cookies)

    def test_employee_login_rejects_unlinked_account_without_creating_session(self):
        user = User.objects.create_user(username="unlinked", password="pw")
        client = Client()
        response = client.post(
            "/api/session-login/",
            {"username": user.username, "password": "pw"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse("sessionid" in client.cookies)

    def test_employee_portal_has_all_module_tabs(self):
        user = User.objects.create_user(username="portal-employee", password="pw")
        Employee.objects.create(
            first_name="Portal",
            last_name="Employee",
            email="portal-employee@example.com",
            user=user,
        )
        self.client.force_login(user)
        response = self.client.get("/employee/")
        self.assertEqual(response.status_code, 200)
        for label in ("Attendance", "Leave Requests", "Salary Advance", "Complaints"):
            self.assertContains(response, label)

    def test_employee_email_login_reaches_employee_portal(self):
        user = User.objects.create_user(
            username="listed@example.com", email="listed@example.com", password="pw"
        )
        Employee.objects.create(
            first_name="Listed",
            last_name="Employee",
            email="listed@example.com",
            user=user,
        )
        client = Client()
        response = client.post(
            "/api/session-login/",
            {"username": "listed@example.com", "password": "pw"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["next_url"], "/employee/")
        self.assertEqual(client.get("/employee/").status_code, 200)

    def test_signup_and_auth_redirect_to_login(self):
        for path in ["/signup/", "/auth/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "/login/")

    def test_static_assets_serve_successfully(self):
        for static_path in [
            "/static/css/main.css",
            "/static/js/dashboard.js",
            "/static/images/kumon-logo.png",
        ]:
            response = self.client.get(static_path)
            self.assertEqual(
                response.status_code, 200, f"Static asset {static_path} failed to load."
            )


class OvertimeNotificationTests(TestCase):
    def setUp(self):
        self.employee = Employee.objects.create(
            first_name="Over", last_name="Time", email="ot-notify@example.com"
        )
        clock_in = timezone.now() - timezone.timedelta(hours=10)
        self.attendance = Attendance.objects.create(
            employee=self.employee,
            date=clock_in.date(),
            clock_in=clock_in,
            clock_out=clock_in + timezone.timedelta(hours=9),
        )

    def _slip(self, status="Pending"):
        from .models import OvertimeSlip

        return OvertimeSlip.objects.create(
            employee=self.employee,
            attendance=self.attendance,
            date=self.attendance.date,
            hours="1.00",
            status=status,
        )

    def test_overtime_approval_creates_payroll_notification(self):
        from .models import Notification

        slip = self._slip()
        self.assertFalse(
            Notification.objects.filter(employee=self.employee, kind="payroll").exists()
        )
        slip.status = "Approved"
        slip.save()
        note = Notification.objects.filter(
            employee=self.employee, kind="payroll"
        ).latest("created_at")
        self.assertIn("Overtime approved", note.text)
        self.assertIn("1.00h", note.text)

    def test_overtime_pending_create_sends_no_notification(self):
        from .models import Notification

        self._slip()
        self.assertFalse(
            Notification.objects.filter(employee=self.employee, kind="payroll").exists()
        )


class NewFeatureAuditTests(TestCase):
    def test_allocation_create_writes_audit_row(self):
        employee = Employee.objects.create(
            first_name="Al", last_name="Loc", email="al-loc@example.com"
        )
        LeaveAllocation.objects.create(
            employee=employee, leave_type="Vacation", year=2026, days_total=5
        )
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=employee, action__icontains="allocation"
            ).exists()
        )

    def test_overtime_request_and_approve_write_audit_rows(self):
        employee = Employee.objects.create(
            first_name="Ot", last_name="Aud", email="ot-aud@example.com"
        )
        clock_in = timezone.now() - timezone.timedelta(hours=10)
        attendance = Attendance.objects.create(
            employee=employee,
            date=clock_in.date(),
            clock_in=clock_in,
            clock_out=clock_in + timezone.timedelta(hours=9),
        )
        slip = OvertimeSlip.objects.create(
            employee=employee,
            attendance=attendance,
            date=attendance.date,
            hours="1.00",
        )
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=employee, action__icontains="overtime requested"
            ).exists()
        )
        slip.status = "Approved"
        slip.save()
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=employee, action__icontains="overtime approved"
            ).exists()
        )
