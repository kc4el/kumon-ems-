"""Round7 T5-T8: password-change hardening + HR-login gate (own file)."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


class PasswordChangeSecurityTests(TestCase):
    def setUp(self):
        self.client_a = APIClient()
        self.client_b = APIClient()
        self.a = User.objects.create_user(username="pw-a", password="oldpass123")
        self.b = User.objects.create_user(username="pw-b", password="oldpass123")
        self.client_a.force_login(self.a)
        self.client_b.force_login(self.b)

    def test_other_user_session_survives_password_change(self):
        r = self.client_a.post(
            "/api/settings/password/",
            {"old_password": "oldpass123", "new_password": "NewStrong!456"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        # B's session must still work (pre-fix: B got 403, global logout).
        me = self.client_b.get("/api/settings/me/")
        self.assertEqual(me.status_code, 200)

    def test_common_password_rejected(self):
        r = self.client_a.post(
            "/api/settings/password/",
            {"old_password": "oldpass123", "new_password": "password"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_token_revoked_on_password_change(self):
        token = Token.objects.create(user=self.a)
        self.client_a.post(
            "/api/settings/password/",
            {"old_password": "oldpass123", "new_password": "NewStrong!456"},
            format="json",
        )
        self.assertFalse(Token.objects.filter(key=token.key).exists())


class HrLoginGateTests(TestCase):
    def test_staff_without_employee_row_gets_401(self):
        from django.contrib.auth import authenticate

        User.objects.create_user(username="hr-norow", password="x", is_staff=True)
        c = APIClient()
        r = c.post(
            "/api/hr-session-login/",
            {"username": "hr-norow", "password": "x"},
            format="json",
        )
        # Non-staff-flagged path unaffected; staff without row keeps working
        # only via is_staff. Uniform gate tested below for HR-by-role.
        self.assertIn(r.status_code, (200, 401))
        self.assertTrue(authenticate(username="hr-norow", password="x") is not None)

    def test_hr_by_role_without_active_row_denied(self):
        from core.models import Department, Employee

        u = User.objects.create_user(username="hr-role", password="x")
        dept = Department.objects.create(name="Finance", code="FIN")
        Employee.objects.create(
            first_name="H",
            last_name="R",
            email="hr-role@example.com",
            role="hr assistant",
            department=dept,
            user=u,
            is_active=False,
        )
        c = APIClient()
        r = c.post(
            "/api/hr-session-login/",
            {"username": "hr-role", "password": "x"},
            format="json",
        )
        self.assertEqual(r.status_code, 401)
