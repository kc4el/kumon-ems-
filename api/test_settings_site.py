"""T8: SiteSetting as source of truth (OT bounds, purge fallback, upload cap)."""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Attendance, Employee, SiteSetting


def make_attendance(employee, hours):
    clock_in = timezone.now() - timedelta(days=1)
    return Attendance.objects.create(
        employee=employee,
        date=clock_in.date(),
        clock_in=clock_in,
        clock_out=clock_in + timedelta(hours=hours),
    )


class OvertimeMaxSettingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="ot-site", password="x", is_staff=True)
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            first_name="Over", last_name="Max", email="otmax@example.com"
        )

    def _post_slip(self, attendance, **overrides):
        payload = {
            "employee": str(self.employee.id),
            "attendance": str(attendance.id),
            "date": str(attendance.date),
        }
        payload.update(overrides)
        return self.client.post("/api/overtime/", payload, format="json")

    def test_raised_max_allows_larger_multiplier(self):
        SiteSetting.objects.update_or_create(
            key="overtime_min_hours", defaults={"value": "0.01"}
        )
        SiteSetting.objects.update_or_create(
            key="overtime_max_hours", defaults={"value": "8.00"}
        )
        r = self._post_slip(make_attendance(self.employee, 14), multiplier="6.00")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["multiplier"], "6.00")

    def test_default_max_still_rejects_above_five(self):
        r = self._post_slip(make_attendance(self.employee, 14), multiplier="6.00")
        self.assertEqual(r.status_code, 400)


class PurgeRetentionFallbackTests(TestCase):
    def test_default_fallback_is_30(self):
        from core.management.commands.purge_resigned import (
            _retention_days_default,
        )

        self.assertEqual(_retention_days_default(), 30)

    def test_site_setting_overrides_default(self):
        from core.management.commands.purge_resigned import (
            _retention_days_default,
        )

        SiteSetting.objects.update_or_create(
            key="purge_retention_days", defaults={"value": "45"}
        )
        self.assertEqual(_retention_days_default(), 45)

    def test_dry_run_without_days_flag_uses_setting(self):
        from unittest.mock import patch

        SiteSetting.objects.update_or_create(
            key="purge_retention_days", defaults={"value": "45"}
        )
        emp = Employee.objects.create(
            first_name="Old",
            last_name="Gone",
            email="oldgone@example.com",
            is_active=False,
            resigned_at=timezone.localdate() - timedelta(days=44),
        )
        out = StringIO()
        with patch("core.management.commands.purge_resigned.supabase"):
            call_command("purge_resigned", dry_run=True, stdout=out)
        # 44 days ago: within a 45-day retention window -> not a candidate.
        self.assertNotIn("would purge", out.getvalue())
        self.assertNotIn(str(emp.email), out.getvalue())
