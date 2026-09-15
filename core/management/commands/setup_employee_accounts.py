from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Employee


class Command(BaseCommand):
    help = "Create or update Django login accounts for employees without linked accounts."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="Employee2026!")
        parser.add_argument("--all", action="store_true", help="Include already-linked employee accounts.")

    def handle(self, *args, **options):
        User = get_user_model()
        password = options["password"]
        queryset = Employee.objects.filter(is_active=True).order_by("email")
        created = 0
        linked = 0
        for employee in queryset:
            if employee.user_id and not options["all"]:
                continue
            username = employee.email.strip().lower()
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": employee.email,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "is_active": True,
                    "is_staff": False,
                },
            )
            user.email = employee.email
            user.first_name = employee.first_name
            user.last_name = employee.last_name
            user.is_active = True
            user.is_staff = False
            user.set_password(password)
            user.save(update_fields=["email", "first_name", "last_name", "is_active", "is_staff", "password"])
            if employee.user_id != user.pk:
                employee.user = user
                employee.save(update_fields=["user"])
                linked += 1
            if user_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Employee accounts ready: {created} created, {linked} employee profiles linked."
            )
        )
        self.stdout.write(f"Employee login: /login/\nShared demo password: {password}")
