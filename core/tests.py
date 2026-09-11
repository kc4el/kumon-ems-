from datetime import date, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from .models import (
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
