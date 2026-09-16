import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Employee, EmployeeAuditLog
from core.supabase_client import supabase

logger = logging.getLogger(__name__)

PURGE_RETENTION_DEFAULT_DAYS = 30


def _retention_days_default():
    """purge_retention_days SiteSetting (source of truth), else 30."""
    try:
        from core.models import SiteSetting

        raw = (
            SiteSetting.objects.filter(key="purge_retention_days")
            .values_list("value", flat=True)
            .first()
        )
        if raw not in (None, ""):
            days = int(float(raw))
            if 1 <= days <= 365:
                return days
    except Exception:
        pass
    return PURGE_RETENTION_DEFAULT_DAYS


class Command(BaseCommand):
    help = (
        "Hard-delete employees resigned 30+ days ago (local row + Supabase auth user)."
        " Doubles as the retry for resign-time deauth failures."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        # Default None: falls back to the purge_retention_days SiteSetting
        # (source of truth, default 30) when the flag is omitted.
        parser.add_argument("--days", type=int, default=None)

    def handle(self, *args, **options):
        days = options.get("days")
        if days is None:
            days = _retention_days_default()
        if days < 0:
            raise CommandError("--days must be >= 0.")
        cutoff = timezone.localdate() - timedelta(days=days)
        query = Employee.objects.filter(is_active=False, resigned_at__lte=cutoff)
        for emp in query:
            if options["dry_run"]:
                self.stdout.write(f"would purge {emp.id} {emp.email}")
                continue
            try:
                with transaction.atomic():
                    supabase.auth.admin.delete_user(str(emp.id))
                    EmployeeAuditLog.objects.create(
                        employee=None,
                        # Snapshot BOTH id and email: the row is about to be
                        # hard-deleted, so the FK cannot carry identity and an
                        # email alone is reusable/ambiguous.
                        action=(
                            f"purged {emp.id} {emp.email} "
                            f"(resigned {emp.resigned_at})"
                        ),
                    )
                    emp.delete()
            except Exception:
                logger.exception("purge: skipping %s after Supabase failure", emp.id)
                self.stderr.write(f"skipped {emp.email}: upstream delete failed")
            else:
                self.stdout.write(f"purged {emp.email}")
