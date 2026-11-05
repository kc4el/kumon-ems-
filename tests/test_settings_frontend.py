"""T9+T15 settings frontend smoke tests (own file — do not touch api/test_settings.py).

Asserts the settings tab markup exists in the dashboard template and the
settings JS hooks exist in dashboard.js. No DB access needed.
"""

import os
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "core" / "index.html"
DASHBOARD_JS = REPO / "static" / "js" / "dashboard.js"
MAIN_CSS = REPO / "static" / "css" / "main.css"


class SettingsFrontendTests(SimpleTestCase):
    def test_pooler_connections_default_to_request_lifetime(self):
        from kumon_ems.settings import _database_connection_max_age

        with patch.dict(os.environ):
            os.environ.pop("DB_CONN_MAX_AGE", None)
            self.assertEqual(
                _database_connection_max_age("aws-0-ap-northeast-1.pooler.supabase.com"),
                0,
            )
            self.assertEqual(
                _database_connection_max_age("db.example.supabase.co"),
                60,
            )

    def test_database_connection_age_can_be_overridden(self):
        from kumon_ems.settings import _database_connection_max_age

        with patch.dict("os.environ", {"DB_CONN_MAX_AGE": "25"}):
            self.assertEqual(
                _database_connection_max_age("aws-0-ap-northeast-1.pooler.supabase.com"),
                25,
            )

    def test_template_has_settings_nav_and_view(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('data-view="settings"', html)
        self.assertIn('id="view-settings"', html)

    def test_template_company_tab_is_staff_only_hidden(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("data-staff-only", html)
        # Company pane + tab both carry the staff-only hidden marker.
        self.assertGreaterEqual(html.count("data-staff-only"), 2)

    def test_template_has_import_dry_run_results(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("settingsImportFile", html)
        self.assertIn("settingsImportDryRun", html)
        self.assertIn("settingsImportResults", html)

    def test_dashboard_js_has_settings_loader_and_a11y(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("loadSettingsView", js)
        self.assertIn("fs-scale", js)
        self.assertIn("applySettingsA11yOnLoad", js)
        self.assertIn("/api/settings/me/", js)
        self.assertIn("/api/settings/site/", js)
        self.assertIn("/api/settings/password/", js)

    def test_main_css_has_a11y_tail_rules(self):
        css = MAIN_CSS.read_text(encoding="utf-8")
        self.assertIn("--fs-scale", css)
        self.assertIn("data-contrast", css)
        self.assertIn("data-motion", css)


LOGIN_HTML = REPO / "core" / "templates" / "core" / "login.html"
NEW_STAFF_HTML = REPO / "core" / "templates" / "core" / "new_staff_login.html"
HR_LOGIN_HTML = REPO / "core" / "templates" / "core" / "hr_login.html"


class Round7UxCopyTests(SimpleTestCase):
    """T1+T4+T12: honest auth copy, plain words, no live credentials."""

    def test_login_omits_redundant_password_recovery_link(self):
        html = LOGIN_HTML.read_text(encoding="utf-8")
        self.assertNotIn("Forgot password?", html)

    def test_login_options_are_labeled_for_each_employee_stage(self):
        html = LOGIN_HTML.read_text(encoding="utf-8")
        self.assertNotIn("newly onboarded staff", html)
        self.assertIn("Remember my sign-in ID", html)
        self.assertIn("Employee ID or linked email", html)
        self.assertIn("Sign in with your Employee ID or linked email and password.", html)
        self.assertIn('placeholder="EMP-XXXX or your email"', html)
        self.assertNotIn("Sign in with Google", html)
        self.assertNotIn("or sign in with your password", html)
        self.assertNotIn("First-time employee? New staff login", html)
        self.assertNotIn("HR Administrator? Use HR Login", html)

        staff_html = NEW_STAFF_HTML.read_text(encoding="utf-8")
        self.assertIn("New staff sign in", staff_html)
        self.assertIn("Temporary password from HR", staff_html)
        self.assertIn("Use the Employee ID and temporary password provided by HR.", staff_html)
        self.assertIn(
            "You can link your Google/email account later in your profile settings.",
            staff_html,
        )
        self.assertIn('placeholder="Enter your temporary password"', staff_html)
        self.assertIn("Sign In to Portal</button>", staff_html)
        self.assertNotIn("Continue to Google account setup", staff_html)
        self.assertNotIn("HR Administrator? Use HR Login", staff_html)
        self.assertNotIn("Go to employee login", staff_html)

    def test_login_page_has_no_self_registration_option(self):
        html = LOGIN_HTML.read_text(encoding="utf-8")
        self.assertNotIn("Create account / Sign up", html)
        self.assertNotIn("authScreenSignup", html)
        self.assertNotIn("handleAuthSignup", html)

    def test_login_pages_are_separated_without_cross_role_links(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Welcome back", html)
        self.assertNotIn("Sign in with Google", html)
        self.assertNotIn("or sign in with your password", html)
        self.assertIn("Employee ID or linked email", html)
        self.assertNotIn("First-time employee? New staff login", html)
        self.assertNotIn("HR Administrator? Use HR Login", html)
        self.assertNotIn("Create account / Sign up", html)

        hr_response = self.client.get("/hr/login/")
        self.assertEqual(hr_response.status_code, 200)
        hr_html = hr_response.content.decode()
        self.assertNotIn("Go to employee login", hr_html)
        self.assertNotIn("Employee account?", hr_html)

    def test_employee_settings_support_optional_google_linking(self):
        portal = (REPO / "core" / "templates" / "core" / "employee_portal.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="portalGoogleAccountStatus"', portal)
        self.assertIn('href="/api/auth/google/link/"', portal)
        self.assertIn("Link Google account", portal)

    def test_hr_roster_shows_employee_id_and_routes_new_hires_to_onboarding(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        dashboard = (REPO / "core" / "templates" / "core" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("emp.employee_id", js)
        self.assertIn("Employee ID:", js)
        self.assertNotIn("onboardingModal", dashboard)
        self.assertIn('href="/hr/onboarding/"', dashboard)
        self.assertIn("Add / Onboard New Employee", dashboard)
        self.assertEqual(dashboard.count("Add / Onboard New Employee"), 1)
        self.assertIn('class="penpot-subnav-row employee-manage-subnav-row"', dashboard)

    def test_hr_handover_is_created_only_from_the_new_hire_form(self):
        template = (REPO / "core" / "templates" / "core" / "hr_onboarding.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="newHireForm"', template)
        self.assertIn('name="first_name"', template)
        self.assertIn('name="last_name"', template)
        self.assertIn('name="email"', template)
        self.assertIn('name="department"', template)
        self.assertIn('name="role"', template)
        self.assertIn('name="date_hired"', template)
        self.assertIn('id="credentialHandover"', template)
        self.assertIn("Copy or print these credentials.", template)
        self.assertIn("For security, the temporary password will not be shown again.", template)

    def test_new_staff_login_url_renders_dedicated_login(self):
        response = self.client.get("/onboarding/login/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("New staff sign in", html)
        self.assertIn("onboardingEmployeeId", html)
        self.assertIn("onboardingTemporaryPassword", html)

        alias_resp = self.client.get("/new-staff/login/")
        self.assertEqual(alias_resp.status_code, 200)
        alias_html = alias_resp.content.decode()
        self.assertIn("New staff sign in", alias_html)

    def test_company_login_doors_guidance(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Not sure which login?", html)


class Round7UxDisplayTests(SimpleTestCase):
    """T2+T3+T11: empty state, readable type, honest loading."""

    def test_no_sub_10px_font_sizes(self):
        import re

        css = MAIN_CSS.read_text(encoding="utf-8")
        small = [
            float(m)
            for m in re.findall(r"font-size:\s*([0-9.]+)px", css)
            if float(m) < 10
        ]
        self.assertEqual(small, [])

    def test_dashboard_empty_state_cta(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("firstEmployeeCta", js)
        self.assertIn("No employees yet", js)

    def test_company_pane_honest_loading(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Contact your HR admin", html)
        self.assertIn("settingsLoadError", html)
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("settingsLoadError", js)
