"""T0: role is read-only in self-service (SEC-H1)."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Employee


class SelfServiceRoleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="r", password="x")
        self.emp = Employee.objects.create(
            first_name="R",
            last_name="O",
            email="r@example.com",
            role="Staff",
            user=self.user,
        )
        self.client.force_authenticate(self.user)

    def test_role_change_ignored(self):
        r = self.client.patch(
            "/api/settings/me/", {"profile": {"role": "hr"}}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.role, "Staff")

    def test_name_email_still_editable(self):
        r = self.client.patch(
            "/api/settings/me/",
            {"profile": {"first_name": "Ren", "email": "ren@example.com"}},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.first_name, "Ren")
