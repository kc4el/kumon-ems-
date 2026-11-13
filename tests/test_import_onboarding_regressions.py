import json
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import AccountCredential, Employee
from tests.test_settings_import import URL, xlsx_file


@override_settings(ROOT_URLCONF="tests.test_settings_import")
class ImportOnboardingRegressionTests(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(username="import-hr", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.hr)

    def test_import_credentials_activate_account_and_are_not_cached(self):
        response = self.client.post(URL, {"file": xlsx_file([
            ["Ada", "Lovelace", "ada@example.com", "Engineer", ""],
            ["", "Invalid", "bad@example.com", "", ""],
        ])}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(response["Pragma"], "no-cache")
        data = response.json()
        self.assertEqual(data["created"], 1)
        self.assertEqual(data["failed"][0]["row"], 3)
        issued = data["credentials"][0]
        self.assertEqual(issued["row"], 2)
        employee = Employee.objects.get(pk=issued["employee_record_id"])
        credential = AccountCredential.objects.get(employee=employee)
        self.assertEqual(employee.status, Employee.OnboardingStatus.PENDING_ONBOARDING)
        self.assertTrue(employee.force_password_change)
        self.assertFalse(employee.user.has_usable_password())
        self.assertTrue(check_password(issued["temporary_password"], credential.password_hash))
        self.assertGreater(credential.expires_at, timezone.now())
        self.client.force_authenticate(user=None)
        login = self.client.post("/api/auth/employee-login", {
            "employee_id": issued["employee_id"],
            "temporary_password": issued["temporary_password"],
        }, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertFalse(AccountCredential.objects.filter(pk=credential.pk).exists())

    def test_failed_credential_write_rolls_back_only_its_row(self):
        create = AccountCredential.objects.create
        with patch.object(AccountCredential.objects, "create", side_effect=[RuntimeError("failure"), None]) as mocked:
            def create_second(**kwargs):
                if mocked.call_count == 1:
                    raise RuntimeError("failure")
                return create(**kwargs)
            mocked.side_effect = create_second
            response = self.client.post(URL, {"file": xlsx_file([
                ["First", "Person", "first@example.com", "", ""],
                ["Second", "Person", "second@example.com", "", ""],
            ])}, format="multipart")
        self.assertEqual(response.json()["created"], 1)
        self.assertEqual(response.json()["failed"][0]["row"], 2)
        self.assertFalse(Employee.objects.filter(email="first@example.com").exists())
        self.assertFalse(User.objects.filter(email="first@example.com").exists())
        self.assertTrue(Employee.objects.filter(email="second@example.com").exists())

    def test_dry_run_does_not_issue_credentials(self):
        with patch("core.views_import.provision_employee") as provision:
            response = self.client.post(URL + "?dry_run=1", {"file": xlsx_file([
                ["Ada", "Lovelace", "ada@example.com", "", ""],
            ])}, format="multipart")
        self.assertTrue(response.json()["rows"][0]["ok"])
        provision.assert_not_called()

    def test_impossible_hire_date_returns_bad_request(self):
        response = self.client.post("/api/hr/employees/onboard/", data=json.dumps({
            "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com",
            "date_hired": "2026-02-30",
        }), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Employee.objects.filter(email="ada@example.com").exists())
