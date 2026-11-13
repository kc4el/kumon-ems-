"""Integration regressions for current sessions and recipient-scoped badge counts."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Employee, Notification, UserSetting


class AccountNotificationRegressions(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="account-regression", password="Original-Passphrase-294!"
        )
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_password_change_preserves_caller_and_revokes_other_sessions_and_token(self):
        other_session = APIClient()
        other_session.force_login(self.user)
        Token.objects.create(user=self.user)
        response = self.client.post("/api/settings/password/", {
            "old_password": "Original-Passphrase-294!",
            "new_password": "Updated-Passphrase-827!",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/settings/me/").status_code, 200)
        self.assertIn(other_session.get("/api/settings/me/").status_code, (401, 403))
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_unread_count_includes_all_pages_and_excludes_other_users_and_muted_kinds(self):
        employee = Employee.objects.create(user=self.user, first_name="Test", last_name="Owner", email="badge-owner@example.com")
        foreign_user = get_user_model().objects.create_user(username="other-badge-user")
        foreign = Employee.objects.create(user=foreign_user, first_name="Test", last_name="Other", email="badge-other@example.com")
        for index in range(15):
            Notification.objects.create(employee=employee, text=f"Read {index}", kind="leave", is_read=True)
        for _ in range(2):
            Notification.objects.create(employee=employee, text="Unread", kind="leave")
        Notification.objects.create(employee=employee, text="Muted", kind="payroll")
        Notification.objects.create(employee=foreign, text="Private", kind="leave")
        setting = UserSetting.objects.get(user=self.user)
        setting.muted_kinds = ["payroll"]
        setting.save(update_fields=["muted_kinds"])
        response = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"unread_count": 2})

    def test_anonymous_unread_count_is_denied(self):
        self.client.logout()
        self.assertIn(self.client.get("/api/notifications/unread-count/").status_code, (401, 403))
