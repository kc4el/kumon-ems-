"""Shared backfill helper for the Employee.user link (migration 0019 + tests).

Kept in a stable module so the data migration stays a thin wrapper and the
behaviour is unit-testable without importing a numbered migration module.
"""

from django.contrib.auth import get_user_model
from django.db import transaction


def backfill_employee_users():
    """Attach each auth User to the Employee with a matching email.

    Returns (matched, unmatched) and prints the counts so both the
    migration output and test runs show what happened. Users whose email
    matches no employee (or whose employee is already linked) count as
    unmatched and are left for staff to attach manually.
    """
    from .models import Employee

    User = get_user_model()
    matched = 0
    unmatched = 0
    with transaction.atomic():
        for user in User.objects.all():
            email = (user.email or "").strip()
            if not email:
                unmatched += 1
                continue
            employee = Employee.objects.filter(
                email__iexact=email, user__isnull=True
            ).first()
            if employee is None:
                unmatched += 1
                continue
            employee.user = user
            employee.save(update_fields=["user"])
            matched += 1
    print(f"backfill Employee.user: matched={matched} unmatched={unmatched}")
    return matched, unmatched
