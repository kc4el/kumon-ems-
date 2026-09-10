import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Employee
from core.supabase_client import supabase

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Hard-delete employees resigned 30+ days ago (local row + Supabase auth user)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        cutoff = timezone.now().date() - timedelta(days=options["days"])
        query = Employee.objects.filter(is_active=False, resigned_at__lte=cutoff)
        for emp in query:
            if options["dry_run"]:
                self.stdout.write(f"would purge {emp.id} {emp.email}")
                continue
            try:
                supabase.auth.admin.delete_user(str(emp.id))
            except Exception:
                logger.exception("purge: Supabase delete failed for %s", emp.id)
            emp.delete()
            self.stdout.write(f"purged {emp.email}")
