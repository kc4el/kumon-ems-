from django.contrib.auth.models import User
from django.test import TestCase


class UserSettingTests(TestCase):
    def test_setting_row_auto_created_with_defaults(self):
        from core.models import UserSetting

        u = User.objects.create_user(username="s", password="x")
        s = UserSetting.objects.get(user=u)
        self.assertEqual(s.page_size, 10)
        self.assertEqual(s.muted_kinds, [])


class SettingsEndpointTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.me = User.objects.create_user(username="me", password="x")
        self.staff = User.objects.create_user(
            username="hr", password="x", is_staff=True
        )

    def test_anon_me_401(self):
        self.assertEqual(self.client.get("/api/settings/me/").status_code, 403)

    def test_me_round_trip(self):
        self.client.force_authenticate(self.me)
        r = self.client.patch("/api/settings/me/", {"page_size": 25}, format="json")
        self.assertEqual(r.status_code, 200)
        self.me.setting.refresh_from_db()
        self.assertEqual(self.me.setting.page_size, 25)

    def test_page_size_preference_applies(self):
        from core.models import Department

        for i in range(12):
            Department.objects.create(name=f"D{i:02d}", code=f"X{i:02d}")
        self.client.force_authenticate(self.me)
        r = self.client.get("/api/departments/")
        self.assertEqual(len(r.json()["results"]), 10)
        self.client.patch("/api/settings/me/", {"page_size": 25}, format="json")
        self.me.setting.refresh_from_db()
        r = self.client.get("/api/departments/")
        self.assertEqual(len(r.json()["results"]), 12)

    def test_nonstaff_site_write_403(self):
        self.client.force_authenticate(self.me)
        r = self.client.patch(
            "/api/settings/site/",
            {"purge_retention_days": "45"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_staff_site_write_200(self):
        self.client.force_authenticate(self.staff)
        r = self.client.patch(
            "/api/settings/site/",
            {"purge_retention_days": "45"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

    def test_password_change_wrong_old_400(self):
        self.client.force_authenticate(self.me)
        r = self.client.post(
            "/api/settings/password/",
            {"old_password": "nope", "new_password": "longenough1"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_site_write_logs_audit(self):
        from core.models import EmployeeAuditLog

        staff_emp = None
        from core.models import Employee

        staff_emp = Employee.objects.create(
            first_name="H",
            last_name="R",
            email="hr@example.com",
            user=self.staff,
        )
        self.client.force_authenticate(self.staff)
        self.client.patch(
            "/api/settings/site/",
            {"purge_retention_days": "45"},
            format="json",
        )
        self.assertTrue(
            EmployeeAuditLog.objects.filter(
                employee=staff_emp, action__contains="purge_retention_days"
            ).exists()
        )
