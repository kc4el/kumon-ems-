from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import EmployeeAuditLog, SiteSetting


class AtomicSettingsTests(TestCase):
    def test_invalid_later_setting_preserves_all_settings_and_audit(self):
        user = get_user_model().objects.create_user(username="settings-atomic", is_staff=True)
        client = APIClient(); client.force_authenticate(user)
        row = SiteSetting.objects.create(key="leave_restrict_backdated", value="false")
        before = EmployeeAuditLog.objects.count()
        response = client.patch("/api/settings/site/", {
            "leave_restrict_backdated":"true", "leave_auto_allocate_days":"invalid",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        row.refresh_from_db()
        self.assertEqual(row.value, "false")
        self.assertEqual(EmployeeAuditLog.objects.count(), before)
