from django.core.management.base import BaseCommand

from core.models import Department, Employee


LISTED_EMPLOYEES = (
    ("Sarah", "Chen", "sarah.chen@kumon-ems.com", "Senior Dev", "Engineering", "ENG"),
    ("Marcus", "Williams", "marcus.williams@kumon-ems.com", "Account Exec", "Sales", "SAL"),
    ("David", "Kim", "david.kim@kumon-ems.com", "Analyst", "Finance", "FIN"),
    ("Rachel", "Adams", "rachel.adams@kumon-ems.com", "Brand Lead", "Marketing", "MKT"),
    ("Robert", "Martinez", "robert.martinez@kumon-ems.com", "People Specialist", "HR", "HR"),
    ("Amanda", "Vance", "amanda.vance@kumon-ems.com", "Brand Strategist", "Marketing", "MKT"),
    ("Michael", "Chang", "michael.chang@kumon-ems.com", "DevOps Engineer", "Engineering", "ENG"),
    ("Elena", "Rodriguez", "elena.rodriguez@kumon-ems.com", "HR Specialist", "HR", "HR"),
)


class Command(BaseCommand):
    help = "Create or update the employees represented in the employee directory demo."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        departments = {}
        for _, _, _, _, name, code in LISTED_EMPLOYEES:
            department, _ = Department.objects.get_or_create(
                name=name, defaults={"code": code}
            )
            if department.code != code:
                department.code = code
                department.save(update_fields=["code"])
            departments[name] = department

        for first_name, last_name, email, role, department_name, _ in LISTED_EMPLOYEES:
            employee, was_created = Employee.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "department": departments[department_name],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
                continue
            changed = []
            for field, value in {
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "department": departments[department_name],
            }.items():
                if getattr(employee, field) != value:
                    setattr(employee, field, value)
                    changed.append(field)
            if changed:
                employee.save(update_fields=changed)
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Listed employee roster ready: {created} created, {updated} updated."
            )
        )
