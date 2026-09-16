"""T9+T15 settings frontend smoke tests (own file — do not touch api/test_settings.py).

Asserts the settings tab markup exists in the dashboard template and the
settings JS hooks exist in dashboard.js. No DB access needed.
"""

from pathlib import Path
from django.test import SimpleTestCase

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "core" / "index.html"
DASHBOARD_JS = REPO / "static" / "js" / "dashboard.js"
MAIN_CSS = REPO / "static" / "css" / "main.css"


class SettingsFrontendTests(SimpleTestCase):
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
        self.assertIn('data-contrast', css)
        self.assertIn('data-motion', css)
