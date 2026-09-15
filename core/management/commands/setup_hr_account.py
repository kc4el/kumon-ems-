from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the dedicated HR portal account."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="hr@kumon-ems.com")
        parser.add_argument("--password", default="HrKumon2026!")
        parser.add_argument("--email", default="hr@kumon-ems.com")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"].strip()
        email = options["email"].strip() or username
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_active": True},
        )
        user.email = email
        user.is_staff = True
        user.is_active = True
        user.set_password(options["password"])
        user.save(update_fields=["email", "is_staff", "is_active", "password"])
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"HR account {action}: {username}"))
        self.stdout.write(f"HR login: /hr/login/\nUsername: {username}\nPassword: {options['password']}")
