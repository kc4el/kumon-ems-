from django.contrib.auth.models import User
from base64 import b64decode
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings


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


@override_settings(MEDIA_ROOT="test-profile-pictures")
class ProfilePictureEndpointTests(TestCase):
    PNG = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQ0kAAAAASUVORK5CYII="
    )

    def setUp(self):
        from rest_framework.test import APIClient
        from core.models import Employee

        self.client = APIClient()
        self.user = User.objects.create_user(username="photo-user", password="x")
        self.employee = Employee.objects.create(
            first_name="Photo",
            last_name="User",
            email="photo-user@example.com",
            user=self.user,
        )
        self.client.force_authenticate(self.user)
        upload_patch = patch(
            "core.views.profile_pictures.upload",
            return_value=f"{self.user.id}/portrait.png",
        )
        download_patch = patch(
            "core.views.profile_pictures.download", return_value=self.PNG
        )
        remove_patch = patch("core.views.profile_pictures.remove")
        self.upload_to_supabase = upload_patch.start()
        self.download_from_supabase = download_patch.start()
        self.remove_from_supabase = remove_patch.start()
        self.addCleanup(upload_patch.stop)
        self.addCleanup(download_patch.stop)
        self.addCleanup(remove_patch.stop)

    def test_upload_is_returned_by_settings_and_can_be_removed(self):
        upload = SimpleUploadedFile(
            "portrait.png",
            self.PNG,
            content_type="image/png",
        )
        response = self.client.post(
            "/api/settings/profile-picture/", {"profile_picture": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/settings/profile-picture/", response.json()["profile_picture"])
        self.upload_to_supabase.assert_called_once()

        settings_response = self.client.get("/api/settings/me/")
        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(
            settings_response.json()["profile"]["profile_picture"],
            response.json()["profile_picture"],
        )
        picture_response = self.client.get("/api/settings/profile-picture/")
        self.assertEqual(picture_response.status_code, 200)
        self.assertEqual(picture_response["Content-Type"], "image/png")
        self.download_from_supabase.assert_called_once()

        remove_response = self.client.delete("/api/settings/profile-picture/")
        self.assertEqual(remove_response.status_code, 204)
        self.user.setting.refresh_from_db()
        self.assertFalse(self.user.setting.profile_picture)
        self.remove_from_supabase.assert_called_once()

    def test_rejects_non_image_uploads(self):
        upload = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
        response = self.client.post(
            "/api/settings/profile-picture/", {"profile_picture": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid PNG", response.json()["error"])

    def test_staff_account_without_employee_profile_can_upload(self):
        staff = User.objects.create_user(username="dashboard-staff", password="x", is_staff=True)
        self.client.force_authenticate(staff)
        upload = SimpleUploadedFile(
            "staff-photo.png",
            self.PNG,
            content_type="image/png",
        )
        response = self.client.post(
            "/api/settings/profile-picture/", {"profile_picture": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 200)
        staff.setting.refresh_from_db()
        self.assertTrue(staff.setting.profile_picture)
        profile = self.client.get("/api/settings/me/").json()["profile"]
        self.assertEqual(profile["profile_picture"], response.json()["profile_picture"])
