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
    ExpenseClaim,
    LeaveRequest,
    Message,
    PayrollRun,
    ShiftRoster,
    ShiftSwap,
)
from core.views import get_dm_key
from core.views_docs import SalaryAdvance


class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="employee-a", email="a@example.com", password="test-pass"
        )
        self.other_user = User.objects.create_user(
            username="employee-b", email="b@example.com", password="test-pass"
        )
        self.hr_user = User.objects.create_user(
            username="hr-user",
            email="hr@example.com",
            password="test-pass",
            is_staff=True,
        )
        self.department = Department.objects.create(name="Operations", code="OPS")
        self.employee = Employee.objects.create(
            first_name="Employee",
            last_name="A",
            email="a@example.com",
            user=self.user,
            department=self.department,
        )
        self.other_employee = Employee.objects.create(
            first_name="Employee",
            last_name="B",
            email="b@example.com",
            user=self.other_user,
            department=self.department,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_colleague_json_uses_html_safe_script_data(self):
        Employee.objects.create(
            first_name='</script><script>alert("x")</script>',
            last_name="Injected",
            email="attacker@example.com",
        )
        self.client.force_login(self.user)

        response = self.client.get("/employee/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(r"\u003C/script\u003E", html)
        self.assertNotIn('</script><script>alert("x")</script>', html)

    def test_message_reads_and_writes_require_conversation_membership(self):
        direct_key = get_dm_key(self.employee.pk, self.other_employee.pk)
        Message.objects.create(conversation_key=direct_key, text="private")
        Message.objects.create(conversation_key="dm_a_b", text="legacy private")

        allowed = self.client.get("/api/messages/", {"conversation": direct_key})
        self.assertEqual(allowed.status_code, 200)
        messages = allowed.json()["results"]
        self.assertIn("private", [message["text"] for message in messages])

        legacy = self.client.get("/api/messages/", {"conversation": "dm_a_b"})
        self.assertEqual(legacy.status_code, 200)
        self.assertIn(
            "legacy private",
            [message["text"] for message in legacy.json()["results"]],
        )

        self.client.force_authenticate(self.hr_user)
        forbidden_read = self.client.get(
            "/api/messages/", {"conversation": direct_key}
        )
        self.assertEqual(forbidden_read.status_code, 403)
        forbidden_write = self.client.post(
            "/api/messages/",
            {"conversation_key": direct_key, "text": "not a participant"},
            format="json",
        )
        self.assertEqual(forbidden_write.status_code, 403)

        malformed_write = self.client.post(
            "/api/messages/",
            {"conversation_key": ["not", "a", "key"], "text": "invalid"},
            format="json",
        )
        self.assertEqual(malformed_write.status_code, 400)

    def test_hr_helpdesk_thread_is_private_to_owner_and_hr(self):
        key = f"hr_{self.employee.pk}"
        self.client.post(
            "/api/messages/",
            {"conversation_key": key, "text": "private request"},
            format="json",
        )
        self.client.force_authenticate(self.other_user)
        response = self.client.get("/api/messages/", {"conversation": key})
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.hr_user)
        response = self.client.get("/api/messages/", {"conversation": "hr"})
        self.assertEqual(response.status_code, 200)
        messages = response.json()["results"]
        self.assertIn(
            "private request", [message["text"] for message in messages]
        )
        reply = self.client.post(
            "/api/messages/",
            {"conversation_key": key, "text": "HR response"},
            format="json",
        )
        self.assertEqual(reply.status_code, 201)
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/messages/", {"conversation": key})
        self.assertIn(
            "HR response",
            [message["text"] for message in response.json()["results"]],
        )

    def test_payroll_runs_are_hr_only(self):
        payroll = PayrollRun.objects.create(
            pay_period_start=date(2026, 1, 1),
            pay_period_end=date(2026, 1, 31),
        )

        self.assertEqual(self.client.get("/api/payroll-runs/").status_code, 403)
        self.assertEqual(
            self.client.delete(f"/api/payroll-runs/{payroll.pk}/").status_code, 403
        )

    def test_clock_out_cannot_target_another_employee_or_set_time(self):
        now = timezone.now()
        attendance = Attendance.objects.create(
            employee=self.other_employee,
            date=timezone.localdate(),
            clock_in=now - timedelta(hours=8),
        )

        response = self.client.post(
            "/api/attendance/clock-out/",
            {"employee_id": str(self.other_employee.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        own_attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            clock_in=now - timedelta(hours=7),
        )
        response = self.client.post(
            "/api/attendance/clock-out/",
            {"employee_id": str(self.employee.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        own_attendance.refresh_from_db()
        self.assertIsNotNone(own_attendance.clock_out)
        attendance.refresh_from_db()
        self.assertIsNone(attendance.clock_out)

        response = self.client.post(
            "/api/attendance/clock-out/",
            {
                "employee_id": str(self.employee.pk),
                "clock_out": (now - timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_leave_balance_is_owner_scoped(self):
        response = self.client.get(
            "/api/leave-balances/",
            {"employee": str(self.other_employee.pk), "year": "2026"},
        )
        self.assertEqual(response.status_code, 403)

    def test_self_service_users_cannot_approve_their_records(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 1),
            reason="Personal",
        )
        response = self.client.patch(
            f"/api/leaves/{leave.pk}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "Pending")

        claim = ExpenseClaim.objects.create(
            employee=self.employee, title="Travel", amount="25.00"
        )
        response = self.client.patch(
            f"/api/expense-claims/{claim.pk}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "Pending")

        response = self.client.post(
            f"/api/claims/{claim.pk}/decision/",
            {"decision": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "Pending")

        response = self.client.post(
            "/api/claim-statuses/",
            {"claim_id": "ADV-OTHER", "status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_attendance_correction_and_salary_advance_decisions_are_hr_only(self):
        now = timezone.now()
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            clock_in=now - timedelta(hours=8),
        )
        correction = AttendanceCorrection.objects.create(
            attendance=attendance,
            proposed_clock_out=now,
            reason="Forgot to clock out",
        )
        response = self.client.patch(
            f"/api/attendance-corrections/{correction.pk}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        correction.refresh_from_db()
        self.assertEqual(correction.status, "Pending")

        advance = SalaryAdvance.objects.create(
            employee=self.employee, amount="100.00"
        )
        response = self.client.patch(
            f"/api/advances/{advance.pk}/",
            {"decision": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        advance.refresh_from_db()
        self.assertEqual(advance.status, "Pending")
        self.client.force_authenticate(self.hr_user)
        response = self.client.patch(
            f"/api/advances/{advance.pk}/",
            {"decision": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        advance.refresh_from_db()
        self.assertEqual(advance.status, "Approved")

    def test_shift_swap_only_target_or_hr_can_decide(self):
        day = date(2026, 12, 5)
        requester_roster = ShiftRoster.objects.create(
            employee=self.employee,
            work_date=day,
            start_time="09:00",
            end_time="17:00",
        )
        target_roster = ShiftRoster.objects.create(
            employee=self.other_employee,
            work_date=day,
            start_time="09:00",
            end_time="17:00",
        )
        swap = ShiftSwap.objects.create(
            requester_roster=requester_roster,
            target_roster=target_roster,
        )

        response = self.client.patch(
            f"/api/shift-swaps/{swap.pk}/",
            {"status": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        swap.refresh_from_db()
        self.assertEqual(swap.status, "Pending")
