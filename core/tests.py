from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from .models import Attendance, Department, Employee, EmployeeAuditLog, LeaveRequest


class AuditLogTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name='Operations', code='OPS')
        self.employee = Employee.objects.create(
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            department=self.department,
        )

    def test_employee_creation_logs_an_audit_entry(self):
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains='created',
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
                action__icontains='Clocked IN',
            ).exists()
        )

        attendance.clock_out = timezone.now()
        attendance.save()

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains='Clocked OUT',
            ).exists()
        )

    def test_leave_status_updates_are_logged(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='Annual',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            reason='Family leave',
            status='Pending',
        )

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains='Submitted leave request',
            ).exists()
        )

        leave.status = 'Approved'
        leave.save()

        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.employee,
                action__icontains='Approved',
            ).exists()
        )


class PageViewTests(TestCase):
    def test_dashboard_view_renders_successfully(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'peopleops')
        self.assertContains(response, 'view-dashboard')

    def test_login_view_renders_successfully(self):
        for path in ['/login/', '/signup/', '/auth/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Sign In to Portal')
            self.assertContains(response, 'Complete Registration')

