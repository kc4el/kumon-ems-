from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Attendance, AttendanceQrSession, Department, Employee


class AttendanceQrSessionTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Operations", code="OPS")
        self.user = get_user_model().objects.create_user(
            username="scanner",
            email="scanner@example.com",
            password="Password123!",
        )
        self.employee = Employee.objects.create(
            first_name="Scanny",
            last_name="User",
            email="scanner@example.com",
            department=self.department,
            role="Operations Associate",
            user=self.user,
            is_active=True,
        )

    def test_current_qr_endpoint_creates_token(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("attendance-qr-current"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("token", body)
        self.assertRegex(body["manual_code"], r"^\d{6}$")
        self.assertTrue(AttendanceQrSession.objects.filter(token=body["token"]).exists())

    def test_manual_attendance_code_records_clock_in(self):
        self.client.force_login(self.user)
        session = AttendanceQrSession.objects.create(
            token="manual-code-clock-in-token",
            manual_code="178379",
            expires_at=timezone.now() + timedelta(minutes=5),
            status=AttendanceQrSession.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("attendance-qr-scan"),
            data={"code": "K 178 379"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["event"], "clock_in")
        self.assertEqual(
            AttendanceQrSession.objects.get(pk=session.pk).status,
            AttendanceQrSession.Status.USED,
        )

    def test_qr_scan_records_clock_in(self):
        self.client.force_login(self.user)
        session = AttendanceQrSession.objects.create(
            token="uZ9A2_pQ7-xY4",
            expires_at=timezone.now() + timedelta(minutes=5),
            status=AttendanceQrSession.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("attendance-qr-scan"),
            data={"token": session.token},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["event"], "clock_in")
        self.assertTrue(Attendance.objects.filter(employee=self.employee, date=timezone.localdate()).exists())
        self.assertEqual(AttendanceQrSession.objects.get(pk=session.pk).status, AttendanceQrSession.Status.USED)

    def test_qr_scan_records_clock_out_after_one_hour(self):
        self.client.force_login(self.user)
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            clock_in=timezone.now() - timedelta(hours=1, minutes=1),
        )
        session = AttendanceQrSession.objects.create(
            token="valid-clock-out-token",
            expires_at=timezone.now() + timedelta(minutes=5),
            status=AttendanceQrSession.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("attendance-qr-scan"),
            data={"token": session.token},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["event"], "clock_out")
        self.assertEqual(response.json()["message"], "Clock-out recorded successfully.")
        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.clock_out)
        self.assertGreaterEqual(attendance.clock_out, attendance.clock_in + timedelta(hours=1))
        self.assertEqual(
            AttendanceQrSession.objects.get(pk=session.pk).status,
            AttendanceQrSession.Status.USED,
        )

    def test_employee_portal_scanner_submits_qr_token_to_attendance_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.get("/employee/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/api/attendance/qr/scan/")
        self.assertContains(response, "JSON.stringify(isManualCode ? { code: token } : { token })")
        self.assertContains(response, "/static/js/jsQR.js")
        self.assertContains(response, "window.jsQR(image.data")
        self.assertContains(response, 'id="qrManualToken"')
        self.assertContains(response, "submitManualQrToken(event)")
        self.assertContains(response, "placeholder=\"K 178 379\"")
        self.assertContains(response, "clock_out_too_soon")
        self.assertNotContains(response, "code.includes('kumon')")

    def test_hr_qr_screen_displays_manual_attendance_token(self):
        hr_user = get_user_model().objects.create_user(
            username="hr-admin",
            email="hr-admin@example.com",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(hr_user)

        response = self.client.get("/hr/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="attendanceQrToken"')
        self.assertContains(response, "Enter this code if you can’t scan")
        self.assertContains(response, 'id="attendanceQrCountdown">60 seconds</span>')
        self.assertContains(response, "updateAttendanceQrCountdown")
        self.assertContains(response, 'id="attendanceQrToken" aria-live="polite"')

    def test_qr_scan_rejects_clock_out_within_one_hour(self):
        self.client.force_login(self.user)
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            clock_in=timezone.now() - timedelta(minutes=30),
        )
        session = AttendanceQrSession.objects.create(
            token="valid-clock-out-token",
            expires_at=timezone.now() + timedelta(minutes=5),
            status=AttendanceQrSession.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("attendance-qr-scan"),
            data={"token": session.token},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "clock_out_too_soon")
        self.assertEqual(response.json()["remaining_minutes"], 30)
        self.assertEqual(response.json()["error"], "You can clock out in 30 minutes.")
        attendance.refresh_from_db()
        self.assertIsNone(attendance.clock_out)
        self.assertEqual(
            AttendanceQrSession.objects.get(pk=session.pk).status,
            AttendanceQrSession.Status.ACTIVE,
        )

    def test_qr_event_stream_is_served_as_sse(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("attendance-qr-events"),
            HTTP_ACCEPT="text/event-stream",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response["Content-Type"])

    def test_invalid_qr_token_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("attendance-qr-scan"),
            data={"token": "not-a-real-token"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid qr token", response.json()["error"].lower())
