"""T7: Company pane regrouped into FrappeHR sections (own file)."""

from pathlib import Path
from django.test import SimpleTestCase

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "core" / "templates" / "core" / "index.html"
DASHBOARD_JS = REPO / "static" / "js" / "dashboard.js"


class CompanyPaneSectionsTests(SimpleTestCase):
    def test_five_section_titles_present(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        for title in (
            "Leave rules",
            "Shift rules",
            "Payroll rules",
            "Mobile",
            "System",
        ):
            self.assertIn(title, html)

    def test_dead_inputs_removed(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        for dead in ("setAttGrace", "setLeaveQuota", "setPayAdvanceMax"):
            self.assertNotIn(dead, html)

    def test_new_ids_wired_both_sides(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        for el_id in (
            "setLeaveBackdated",
            "setLeaveAutoDays",
            "setShiftDouble",
            "setMobileCheckin",
        ):
            self.assertIn(el_id, html)
            self.assertIn(el_id, js)
        self.assertIn("shift_allow_double_booking", js)
