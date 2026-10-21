"""Shared constants for the core app.

Importable by models, serializers, and views without circular-import risk.
"""

SITE_SETTING_DEFAULTS = {
    "overtime_min_hours": "0.01",
    "overtime_max_hours": "5.00",
    "purge_retention_days": "30",
    "onboarding_max_mb": "10",
    "leave_restrict_backdated": "false",
    "leave_auto_allocate_days": "0",
    "shift_allow_double_booking": "false",
    "mobile_checkin_enabled": "true",
    "late_grace_period_mins": "15",
    "auto_clockout_hours": "12",
    "break_duration_mins": "60",
    "salary_advance_max_limit": "10000",
    "leave_annual_quota": "15",
    "leave_carry_forward_max": "5",
}

SITE_SETTING_SPECS = {
    "overtime_min_hours": {"min": 0, "max": 24},
    "overtime_max_hours": {"min": 0, "max": 24},
    "purge_retention_days": {"min": 1, "max": 365, "integer": True},
    "onboarding_max_mb": {"min": 1, "max": 100, "integer": True},
    "leave_restrict_backdated": {"bool": True},
    "leave_auto_allocate_days": {"min": 0, "max": 365, "integer": True},
    "shift_allow_double_booking": {"bool": True},
    "mobile_checkin_enabled": {"bool": True},
    "late_grace_period_mins": {"min": 0, "max": 120, "integer": True},
    "auto_clockout_hours": {"min": 1, "max": 24, "integer": True},
    "break_duration_mins": {"min": 0, "max": 180, "integer": True},
    "salary_advance_max_limit": {"min": 100, "max": 500000, "integer": True},
    "leave_annual_quota": {"min": 0, "max": 100, "integer": True},
    "leave_carry_forward_max": {"min": 0, "max": 50, "integer": True},
}

# Derived for model-level clean() validation (numeric keys only).
NUMERIC_RANGES = {
    k: (spec["min"], spec["max"])
    for k, spec in SITE_SETTING_SPECS.items()
    if "min" in spec
}
