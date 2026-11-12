from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from core.models import Attendance, AttendanceQrSession, Employee, EmployeeAuditLog, SiteSetting
from core.qr_service import get_active_qr_session


class SecureAttendanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="worker", password="secret123")
        self.other = get_user_model().objects.create_user(username="other", password="secret123")
        self.hr = get_user_model().objects.create_user(username="hr", password="secret123", is_staff=True)
        self.employee = Employee.objects.create(first_name="Worker", last_name="One", email="one@example.com", user=self.user)
        self.other_employee = Employee.objects.create(first_name="Worker", last_name="Two", email="two@example.com", user=self.other)
        self.client = APIClient()

    def qr(self, token="test-token", code="123456", delta=60):
        return AttendanceQrSession.objects.create(token=token, manual_code=code, expires_at=timezone.now() + timedelta(seconds=delta))

    def test_legacy_credentials_do_not_log_in_or_write(self):
        response = self.client.post(reverse("attendance-check-in"), {"name": "worker", "password": "secret123"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(Attendance.objects.exists())

    def test_legacy_page_redirects_to_sign_in_or_employee_portal(self):
        self.assertRedirects(self.client.get(reverse("attendance-checkin")), "/login/?next=/employee/", fetch_redirect_response=False)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("attendance-checkin")), "/employee/", fetch_redirect_response=False)

    def test_qr_secrets_and_event_stream_are_hr_only(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(reverse("attendance-qr-current")).status_code, 403)
        # The event stream uses Django session authentication.
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("attendance-qr-events")).status_code, 403)
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.get(reverse("attendance-qr-current")).status_code, 200)

    def test_self_service_requires_valid_token_and_cannot_replay_it(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(reverse("attendance-self"), {"action": "clock_in"}, format="json").status_code, 400)
        session = self.qr()
        response = self.client.post(reverse("attendance-self"), {"code": "K 123 456"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["event"], "clock_in")
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(reverse("attendance-qr-scan"), {"token": session.token}, format="json").status_code, 400)
        self.assertFalse(Attendance.objects.filter(employee=self.other_employee).exists())

    def test_expired_disabled_and_inactive_scans_do_not_write(self):
        self.client.force_authenticate(self.user)
        expired = self.qr(delta=-1)
        self.assertEqual(self.client.post(reverse("attendance-qr-scan"), {"token": expired.token}, format="json").status_code, 400)
        session = self.qr(token="second", code="234567")
        SiteSetting.objects.create(key="mobile_checkin_enabled", value="false")
        self.assertEqual(self.client.post(reverse("attendance-qr-scan"), {"token": session.token}, format="json").status_code, 403)
        SiteSetting.objects.filter(key="mobile_checkin_enabled").update(value="true")
        self.employee.is_active = False
        self.employee.save()
        self.assertEqual(self.client.post(reverse("attendance-self"), {"token": session.token}, format="json").status_code, 403)
        self.assertFalse(Attendance.objects.exists())
        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceQrSession.Status.ACTIVE)

    def test_existing_api_token_cannot_bypass_onboarding(self):
        token = Token.objects.create(user=self.user)
        session = self.qr()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        for status_value, force_change in [
            (Employee.OnboardingStatus.PENDING_ONBOARDING, False),
            (Employee.OnboardingStatus.ACTIVE, True),
        ]:
            self.employee.status = status_value
            self.employee.force_password_change = force_change
            self.employee.save()
            response = self.client.post(reverse("attendance-qr-scan"), {"token": session.token}, format="json")
            self.assertEqual(response.status_code, 403)
        session.refresh_from_db()
        self.assertEqual(session.status, AttendanceQrSession.Status.ACTIVE)
        self.assertFalse(Attendance.objects.exists())

    def test_pending_employee_cannot_obtain_api_token(self):
        self.employee.status = Employee.OnboardingStatus.PENDING_ONBOARDING
        self.employee.save()
        response = self.client.post(reverse("api-token"), {"username": "worker", "password": "secret123"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_cooldown_applies_to_self_service_and_preserves_token(self):
        self.client.force_authenticate(self.user)
        row = Attendance.objects.create(employee=self.employee, date=timezone.localdate(), clock_in=timezone.now() - timedelta(minutes=4))
        session = self.qr()
        response = self.client.post(reverse("attendance-self"), {"token": session.token, "action": "clock_out"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "clock_out_too_soon")
        row.refresh_from_db()
        session.refresh_from_db()
        self.assertIsNone(row.clock_out)
        self.assertEqual(session.status, AttendanceQrSession.Status.ACTIVE)

    def test_self_service_can_clock_out_after_one_hour_with_fresh_token(self):
        self.client.force_authenticate(self.user)
        row = Attendance.objects.create(employee=self.employee, date=timezone.localdate(), clock_in=timezone.now() - timedelta(hours=2))
        session = self.qr()
        response = self.client.post(reverse("attendance-self"), {"token": session.token}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["event"], "clock_out")
        row.refresh_from_db()
        session.refresh_from_db()
        self.assertIsNotNone(row.clock_out)
        self.assertEqual(session.status, AttendanceQrSession.Status.USED)

    def test_failed_token_claim_rolls_back_attendance(self):
        self.client.force_authenticate(self.user)
        session = self.qr()
        with patch("core.views.invalidate_qr_session", return_value=None):
            response = self.client.post(reverse("attendance-qr-scan"), {"token": session.token}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Attendance.objects.exists())

    def test_direct_writes_are_hr_only_and_manual_entry_is_audited(self):
        self.client.force_authenticate(self.user)
        row = Attendance.objects.create(employee=self.employee, date=timezone.localdate(), clock_in=timezone.now())
        detail = reverse("attendance-detail", args=[row.pk])
        self.assertEqual(self.client.patch(detail, {"clock_out": timezone.now().isoformat()}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)
        self.assertEqual(self.client.post(reverse("attendance-clock-out"), {}, format="json").status_code, 403)
        response = self.client.post(reverse("attendance-list-create"), {"employee": str(self.other_employee.pk), "date": str(timezone.localdate())}, format="json")
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.hr)
        response = self.client.post(reverse("attendance-clock-out"), {"employee_id": str(self.employee.pk)}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmployeeAuditLog.objects.filter(employee=self.employee, action__contains="manually clocked out").exists())

    def test_current_generation_reuses_live_token_and_rotation_leaves_one_active(self):
        first = get_active_qr_session()
        self.assertEqual(first.pk, get_active_qr_session().pk)
        second = get_active_qr_session(force_new=True)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(AttendanceQrSession.objects.filter(status=AttendanceQrSession.Status.ACTIVE).count(), 1)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentAttendanceTests(TransactionTestCase):
    def test_two_employees_cannot_consume_the_same_token(self):
        users = [get_user_model().objects.create_user(username=f"worker-{i}") for i in range(2)]
        for i, user in enumerate(users):
            Employee.objects.create(first_name="Worker", last_name=str(i), email=f"worker{i}@example.com", user=user)
        session = AttendanceQrSession.objects.create(token="race-token", expires_at=timezone.now() + timedelta(minutes=2))
        barrier = Barrier(2)

        def scan(user):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user)
                barrier.wait(timeout=10)
                return client.post(reverse("attendance-qr-scan"), {"token": session.token}, format="json").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(scan, users))
        self.assertEqual(sorted(statuses), [200, 400])
        self.assertEqual(Attendance.objects.count(), 1)

    def test_simultaneous_initial_generation_returns_one_session(self):
        barrier = Barrier(2)

        def generate(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return get_active_qr_session().pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            sessions = list(executor.map(generate, range(2)))
        self.assertEqual(sessions[0], sessions[1])
        self.assertEqual(AttendanceQrSession.objects.filter(status=AttendanceQrSession.Status.ACTIVE).count(), 1)
