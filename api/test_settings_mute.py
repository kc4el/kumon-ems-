"""T7: muted notification kinds filter (NotificationListView)."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Employee, Notification


class MutedKindsFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="muted-u", password="x")
        self.employee = Employee.objects.create(
            first_name="Mut",
            last_name="Ed",
            email="muted@example.com",
            user=self.user,
        )
        self.client.force_authenticate(self.user)
        self.payroll_note = Notification.objects.create(
            employee=self.employee, text="Payroll posted", kind="payroll"
        )
        self.leave_note = Notification.objects.create(
            employee=self.employee, text="Leave approved", kind="leave"
        )

    def _listed_kinds(self):
        r = self.client.get("/api/notifications/")
        self.assertEqual(r.status_code, 200)
        return [n["kind"] for n in r.json()["results"]]

    def test_mute_payroll_excludes_payroll_note(self):
        setting = self.user.setting
        setting.muted_kinds = ["payroll"]
        setting.save(update_fields=["muted_kinds"])
        kinds = self._listed_kinds()
        self.assertNotIn("payroll", kinds)
        self.assertIn("leave", kinds)

    def test_unmuted_sees_all(self):
        kinds = self._listed_kinds()
        self.assertIn("payroll", kinds)
        self.assertIn("leave", kinds)
