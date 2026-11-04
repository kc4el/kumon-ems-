import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import AccountCredential, Department, Employee, OAuthLink


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="test-client-id",
    GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret",
    GOOGLE_OAUTH_REDIRECT_URI="http://testserver/api/auth/google/callback/",
    GOOGLE_OAUTH_ALLOWED_DOMAIN="",
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "anon": "100/day",
            "user": "1000/day",
            "login": "10/minute",
            "mfa": "5/minute",
            "onboarding_login": "100/minute",
            "onboarding_generate": "100/hour",
        }
    },
)
class EmployeeOnboardingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.hr_user = User.objects.create_user(
            username="onboarding-hr", password="TestPassword123!", is_staff=True
        )
        self.department = Department.objects.create(name="People Operations")
        self.employee = None

    def new_hire_payload(self):
        return {
            "first_name": "New",
            "last_name": "Employee",
            "email": "new.employee@example.com",
            "role": "Coordinator",
            "department": str(self.department.pk),
            "date_hired": "2026-11-10",
        }

    def issue_credentials(self, payload=None):
        self.client.force_login(self.hr_user)
        response = self.client.post(
            "/api/hr/employees/onboard/",
            data=json.dumps(payload or self.new_hire_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.employee = Employee.objects.get(pk=response.json()["employee_record_id"])
        return response.json()

    def sign_in_once(self, credentials):
        return self.client.post(
            "/api/auth/employee-login",
            data=json.dumps(
                {
                    "employee_id": credentials["employee_id"],
                    "temporary_password": credentials["temporary_password"],
                }
            ),
            content_type="application/json",
        )

    def test_hr_credentials_activate_employee_and_allow_direct_portal_login(self):
        credentials = self.issue_credentials()
        self.employee.refresh_from_db()
        account_credential = AccountCredential.objects.get(employee=self.employee)
        self.assertRegex(credentials["employee_id"], r"^EMP-\d{4}-\d{4}$")
        self.assertRegex(credentials["temporary_password"], r"^[A-HJ-NP-Za-km-z2-9]{12}$")
        self.assertTrue(account_credential.password_hash.startswith("argon2$"))
        self.assertTrue(
            check_password(credentials["temporary_password"], account_credential.password_hash)
        )
        self.assertIsNone(account_credential.consumed_at)
        self.assertEqual(self.employee.status, Employee.OnboardingStatus.PENDING_ONBOARDING)
        self.assertTrue(self.employee.force_password_change)
        self.assertEqual(self.employee.employee_id, credentials["employee_id"])
        self.assertEqual(self.employee.role, "Coordinator")
        self.assertEqual(self.employee.department, self.department)
        self.assertEqual(str(self.employee.date_hired), "2026-11-10")
        self.assertFalse(self.employee.user.has_usable_password())

        response = self.sign_in_once(credentials)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["next_url"], "/employee/")
        self.assertFalse(AccountCredential.objects.filter(pk=account_credential.pk).exists())
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.OnboardingStatus.ACTIVE)
        self.assertFalse(self.employee.force_password_change)
        self.assertNotIn("onboarding_employee_id", self.client.session)
        self.assertEqual(self.client.get("/employee/").status_code, 200)
        settings_response = self.client.get("/api/settings/me/")
        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(
            settings_response.json()["google_account"],
            {"linked": False, "email": ""},
        )

        self.client.post(
            "/api/session-logout/",
            data="{}",
            content_type="application/json",
        )
        replay = self.sign_in_once(credentials)
        self.assertEqual(replay.status_code, 401)
        login = self.client.post(
            "/api/session-login/",
            data=json.dumps(
                {
                    "username": credentials["employee_id"],
                    "password": credentials["temporary_password"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200, login.content)

    def test_new_employee_anonymous_login_creates_portal_session(self):
        credentials = self.issue_credentials()
        employee_client = APIClient()
        response = employee_client.post(
            "/api/auth/employee-login/",
            data=json.dumps(
                {
                    "employee_id": credentials["employee_id"],
                    "temporary_password": credentials["temporary_password"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["next_url"], "/employee/")
        self.assertIn("sessionid", response.cookies)
        self.assertEqual(
            employee_client.session.get("_auth_user_id"),
            str(self.employee.user_id),
        )
        portal_response = employee_client.get("/employee/")
        self.assertEqual(portal_response.status_code, 200)

    def test_google_link_verifies_state_nonce_and_activates_employee(self):
        credentials = self.issue_credentials()
        self.assertEqual(self.sign_in_once(credentials).status_code, 200)

        authorization = self.client.get("/api/auth/google/link/")
        self.assertEqual(authorization.status_code, 302)
        params = parse_qs(urlparse(authorization["Location"]).query)
        self.assertEqual(params["scope"], ["openid email profile"])
        state = params["state"][0]
        nonce = params["nonce"][0]

        token_response = Mock()
        token_response.json.return_value = {"id_token": "verified-id-token"}
        claims = {
            "sub": "google-subject-001",
            "email": "new.employee@gmail.com",
            "email_verified": True,
            "nonce": nonce,
        }
        with (
            patch("core.views_onboarding.requests.post", return_value=token_response),
            patch(
                "core.views_onboarding.id_token.verify_oauth2_token",
                return_value=claims,
            ),
        ):
            callback = self.client.get(
                "/api/auth/google/callback/",
                {"state": state, "code": "authorization-code"},
            )

        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/employee/#settingsPanel")
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.OnboardingStatus.ACTIVE)
        self.assertFalse(self.employee.force_password_change)
        self.assertFalse(AccountCredential.objects.filter(employee=self.employee).exists())
        self.assertEqual(
            OAuthLink.objects.get(employee=self.employee).subject,
            "google-subject-001",
        )
        settings_response = self.client.get("/api/settings/me/")
        self.assertEqual(
            settings_response.json()["google_account"],
            {"linked": True, "email": "new.employee@gmail.com"},
        )

    def test_google_callback_rejects_mismatched_state_without_network_request(self):
        credentials = self.issue_credentials()
        self.assertEqual(self.sign_in_once(credentials).status_code, 200)
        self.client.get("/api/auth/google/link/")

        with patch("core.views_onboarding.requests.post") as token_exchange:
            response = self.client.get(
                "/api/auth/google/callback/",
                {"state": "not-the-session-state", "code": "authorization-code"},
            )

        self.assertEqual(response.status_code, 400)
        token_exchange.assert_not_called()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.OnboardingStatus.ACTIVE)
        self.assertFalse(OAuthLink.objects.filter(employee=self.employee).exists())

    def test_google_sign_in_endpoint_is_removed(self):
        response = self.client.get("/api/auth/google/login/")
        self.assertEqual(response.status_code, 404)

    def test_hr_onboarding_page_is_a_new_hire_form_not_an_employee_list(self):
        self.client.force_login(self.hr_user)
        response = self.client.get("/hr/onboarding/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertContains(response, "Add / Onboard New Employee")
        self.assertContains(response, "Generate Emp ID &amp; Temporary Password")
        self.assertContains(response, "Copy Credentials")
        self.assertNotContains(response, "Not assigned")
        self.assertNotContains(response, "<table")
        self.assertIn("temporary password will not be shown again", html)
        self.assertContains(response, "Optional onboarding documents")
        self.assertContains(response, "NBI Clearance")
        self.assertContains(response, "BIR Form 2316")
        self.assertContains(response, "PSA Birth Certificate")
        self.assertContains(response, "Signed Employment Contract")
        self.assertContains(response, "Government Records")
        self.assertContains(response, 'type="file"')
        self.assertContains(response, "/api/onboarding-docs/")

    def test_hr_endpoint_rejects_non_hr_users(self):
        employee_user = User.objects.create_user(
            username="ordinary-employee", password="TestPassword123!"
        )
        self.client.force_login(employee_user)
        response = self.client.post(
            "/api/hr/employees/onboard/",
            data=json.dumps(self.new_hire_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Employee.objects.count(), 0)
        self.assertFalse(AccountCredential.objects.exists())

    def test_hr_endpoint_validates_new_hire_fields(self):
        self.client.force_login(self.hr_user)
        payload = self.new_hire_payload()
        payload["date_hired"] = "not-a-date"
        response = self.client.post(
            "/api/hr/employees/onboard/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Employee.objects.count(), 0)

    def test_existing_employee_credential_regeneration_route_is_removed(self):
        response = self.client.post("/api/hr/employees/generate-credentials/")
        self.assertEqual(response.status_code, 404)

    def test_duplicate_email_does_not_create_another_employee(self):
        self.issue_credentials()
        response = self.client.post(
            "/api/hr/employees/onboard/",
            data=json.dumps(self.new_hire_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(AccountCredential.objects.count(), 1)

    def test_temp_credential_expires(self):
        credentials = self.issue_credentials()
        AccountCredential.objects.filter(employee=self.employee).update(
            expires_at=timezone.now()
        )
        response = self.sign_in_once(credentials)
        self.assertEqual(response.status_code, 401)
