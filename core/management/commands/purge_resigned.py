import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Employee, EmployeeAuditLog
from core.supabase_client import supabase

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Hard-delete employees resigned 30+ days ago (local row + Supabase auth user)."
        " Doubles as the retry for resign-time deauth failures."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        days = options["days"]
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
                        action=f"purged {emp.email} (resigned {emp.resigned_at})",
                    )
                    emp.delete()
            except Exception:
                logger.exception("purge: skipping %s after Supabase failure", emp.id)
                self.stderr.write(f"skipped {emp.email}: upstream delete failed")
            else:
                self.stdout.write(f"purged {emp.email}")
