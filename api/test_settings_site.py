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


class SiteSettingConstraintTests(TestCase):
    """T9: model-level numeric guard + logged reader fallback."""

    def test_non_numeric_value_rejected_by_clean(self):
        from django.core.exceptions import ValidationError

        from core.models import SiteSetting

        with self.assertRaises(ValidationError):
            SiteSetting(key="purge_retention_days", value="banana").full_clean()

    def test_out_of_range_value_rejected_by_clean(self):
        from django.core.exceptions import ValidationError

        from core.models import SiteSetting

        with self.assertRaises(ValidationError):
            SiteSetting(key="purge_retention_days", value="9999").full_clean()

    def test_corrupt_row_falls_back_with_log(self):
        from core.models import SiteSetting
        from core.serializers import _site_decimal
        from decimal import Decimal

        SiteSetting.objects.update_or_create(
            key="overtime_max_hours", defaults={"value": "banana"}
        )
        with self.assertLogs("core.serializers", level="WARNING"):
            self.assertEqual(
                _site_decimal("overtime_max_hours", Decimal("5.00")),
                Decimal("5.00"),
            )


class PurgeRetentionFloorTests(TestCase):
    """T10: --days floor, id snapshot, honest errors."""

    def test_days_zero_rejected(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("purge_resigned", days=0, dry_run=True)

    def test_days_over_max_rejected(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("purge_resigned", days=400, dry_run=True)


class FrappeMirrorKeysTests(TestCase):
    """T1: the 5 FrappeHR-mirror keys validate through the site endpoint."""

    def setUp(self):
        self.client = APIClient()
        user = User.objects.create_user(username="frappe", password="x", is_staff=True)
        self.client.force_authenticate(user=user)

    def test_five_keys_accept_valid_values(self):
        r = self.client.patch(
            "/api/settings/site/",
            {
                "leave_restrict_backdated": "true",
                "leave_auto_allocate_days": "14",
                "shift_allow_double_booking": "false",
                "payroll_round_net": "true",
                "mobile_checkin_enabled": "True",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        for key in (
            "leave_restrict_backdated",
            "leave_auto_allocate_days",
            "shift_allow_double_booking",
            "payroll_round_net",
            "mobile_checkin_enabled",
        ):
            self.assertIn(key, r.json())

    def test_allocate_days_out_of_range_rejected(self):
        r = self.client.patch(
            "/api/settings/site/",
            {"leave_auto_allocate_days": "9999"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_bool_rejects_non_boolean(self):
        r = self.client.patch(
            "/api/settings/site/",
            {"shift_allow_double_booking": "yes"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
