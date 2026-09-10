from datetime import date, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Attendance, Department, Employee, EmployeeAuditLog, LeaveRequest


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


class PageViewTests(TestCase):
    def test_dashboard_view_renders_successfully(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kumon EMS")
        self.assertContains(response, "view-dashboard")

    def test_login_view_renders_successfully(self):
        for path in ["/login/", "/signup/", "/auth/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Sign In to Portal")
            self.assertContains(response, "Complete Registration")

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
