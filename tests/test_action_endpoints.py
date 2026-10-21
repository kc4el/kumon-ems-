from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Attendance,
    AttendanceCorrection,
    Department,
    Employee,
    EmployeeAuditLog,
    LeaveRequest,
    Notification,
    OvertimeSlip,
    ShiftRoster,
    ShiftSwap,
    SiteSetting,
    UserSetting,
)


class ActionEndpointsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username="staff_admin", password="x", is_staff=True
        )
        self.emp_user = User.objects.create_user(
            username="regular_emp", password="x"
        )
        self.target_user = User.objects.create_user(
            username="target_emp", password="x"
        )

        self.dept = Department.objects.create(name="Instructors", code="INST")

        self.emp = Employee.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            user=self.emp_user,
            department=self.dept,
        )
        self.target_emp = Employee.objects.create(
            first_name="Bob",
            last_name="Smith",
            email="bob@example.com",
            user=self.target_user,
            department=self.dept,
        )

    # 1. Leave Actions
    def test_leave_approve_and_reject(self):
        leave = LeaveRequest.objects.create(
            employee=self.emp,
            leave_type="Vacation",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 3),
            reason="Holiday",
            status="Pending",
        )

        # Non-staff should be forbidden (403)
        self.client.force_authenticate(self.emp_user)
        res = self.client.post(f"/api/leaves/{leave.pk}/approve/")
        self.assertEqual(res.status_code, 403)

        # Staff can approve
        self.client.force_authenticate(self.staff_user)
        res = self.client.post(f"/api/leaves/{leave.pk}/approve/")
        self.assertEqual(res.status_code, 200)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "Approved")
        self.assertTrue(
            Notification.objects.filter(employee=self.emp, kind="leave").exists()
        )

        # Staff can reject with reason
        leave.status = "Pending"
        leave.save()
        res = self.client.post(
            f"/api/leaves/{leave.pk}/reject/",
            {"reason": "Peak period"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "Rejected")
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=self.emp, action__contains="Peak period"
            ).exists()
        )

    def test_leave_bulk_decide(self):
        l1 = LeaveRequest.objects.create(
            employee=self.emp,
            leave_type="Sick",
            start_date=date(2026, 11, 5),
            end_date=date(2026, 11, 5),
            status="Pending",
        )
        l2 = LeaveRequest.objects.create(
            employee=self.target_emp,
            leave_type="Sick",
            start_date=date(2026, 11, 6),
            end_date=date(2026, 11, 6),
            status="Pending",
        )

        self.client.force_authenticate(self.staff_user)
        res = self.client.post(
            "/api/leaves/bulk-decide/",
            {"ids": [str(l1.pk), str(l2.pk)], "decision": "Approved"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["updated_count"], 2)
        l1.refresh_from_db()
        l2.refresh_from_db()
        self.assertEqual(l1.status, "Approved")
        self.assertEqual(l2.status, "Approved")

    # 2. Overtime Actions
    def test_overtime_approve_and_reject(self):
        att = Attendance.objects.create(
            employee=self.emp,
            date=date(2026, 11, 1),
            clock_in=timezone.now(),
            clock_out=timezone.now() + timedelta(hours=10),
        )
        slip = OvertimeSlip.objects.create(
            employee=self.emp,
            attendance=att,
            date=att.date,
            hours="2.00",
            status="Pending",
        )

        # Non-staff 403
        self.client.force_authenticate(self.emp_user)
        self.assertEqual(
            self.client.post(f"/api/overtime/{slip.pk}/approve/").status_code, 403
        )

        # Staff approve
        self.client.force_authenticate(self.staff_user)
        res = self.client.post(f"/api/overtime/{slip.pk}/approve/")
        self.assertEqual(res.status_code, 200)
        slip.refresh_from_db()
        self.assertEqual(slip.status, "Approved")

    # 3. Attendance Correction Action
    def test_attendance_correction_approve_adjusts_attendance(self):
        att = Attendance.objects.create(
            employee=self.emp,
            date=date(2026, 11, 2),
            clock_in=timezone.now(),
            clock_out=None,
        )
        fixed_out = att.clock_in + timedelta(hours=8)
        corr = AttendanceCorrection.objects.create(
            attendance=att,
            proposed_clock_out=fixed_out,
            reason="Forgot to punch clock-out",
            status="Pending",
        )

        self.client.force_authenticate(self.staff_user)
        res = self.client.post(f"/api/attendance-corrections/{corr.pk}/approve/")
        self.assertEqual(res.status_code, 200)
        corr.refresh_from_db()
        att.refresh_from_db()
        self.assertEqual(corr.status, "Approved")
        self.assertEqual(att.clock_out, fixed_out)

    # 4. Shift Swap Action
    def test_shift_swap_decide(self):
        r1 = ShiftRoster.objects.create(
            employee=self.emp,
            work_date=date(2026, 11, 10),
            shift_type="Morning",
            start_time="08:00:00",
            end_time="16:00:00",
        )
        r2 = ShiftRoster.objects.create(
            employee=self.target_emp,
            work_date=date(2026, 11, 10),
            shift_type="Evening",
            start_time="16:00:00",
            end_time="23:59:00",
        )
        swap = ShiftSwap.objects.create(
            requester_roster=r1,
            target_roster=r2,
            reason="Appointment",
            status="Pending",
        )

        # Target employee can approve
        self.client.force_authenticate(self.target_user)
        res = self.client.post(
            f"/api/shift-swaps/{swap.pk}/decide/",
            {"decision": "Approved"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        swap.refresh_from_db()
        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertEqual(swap.status, "Approved")
        # Employees are swapped
        self.assertEqual(r1.employee, self.target_emp)
        self.assertEqual(r2.employee, self.emp)

    # 5. Shift Roster Bulk Create
    def test_shift_roster_bulk_create(self):
        self.client.force_authenticate(self.staff_user)
        payload = {
            "shifts": [
                {
                    "employee": str(self.emp.pk),
                    "work_date": "2026-11-15",
                    "shift_type": "Morning",
                    "start_time": "08:00:00",
                    "end_time": "12:00:00",
                },
                {
                    "employee": str(self.target_emp.pk),
                    "work_date": "2026-11-15",
                    "shift_type": "Afternoon",
                    "start_time": "13:00:00",
                    "end_time": "17:00:00",
                },
            ]
        }
        res = self.client.post("/api/shift-rosters/bulk/", payload, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["created_count"], 2)

    # 6. Employee Self-Service & Payout
    def test_employee_me_and_payout(self):
        self.client.force_authenticate(self.emp_user)

        # GET /api/employees/me/
        res = self.client.get("/api/employees/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "jane@example.com")

        # PATCH /api/employees/me/
        res = self.client.patch(
            "/api/employees/me/",
            {"phone_number": "09123456789", "emergency_contact_name": "Mom"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["contact_info"]["phone_number"], "09123456789")

        # PATCH /api/employees/me/payout/
        res = self.client.patch(
            "/api/employees/me/payout/",
            {"bank_name": "BDO", "account_number": "123456789012"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        # GET /api/employees/me/payout/ (masked)
        res = self.client.get("/api/employees/me/payout/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["bank_name"], "BDO")
        self.assertTrue(res.json()["account_number_masked"].startswith("********"))

    # 7. New Policy SiteSettings
    def test_new_policy_sitesettings(self):
        self.client.force_authenticate(self.staff_user)
        res = self.client.patch(
            "/api/settings/site/",
            {"late_grace_period_mins": "20"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            SiteSetting.objects.get(key="late_grace_period_mins").value, "20"
        )
