from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from accounts.views import ROLE_NAMES
from masterdata.models import Department


class Command(BaseCommand):
    help = "Seed local development roles, admin account and master data."

    def handle(self, *args, **options):
        for role_name in ROLE_NAMES:
            Group.objects.get_or_create(name=role_name)

        admin_email = "admin@bou.or.ug"
        admin, created = User.objects.get_or_create(
            username=admin_email,
            defaults={
                "email": admin_email,
                "first_name": "BOU",
                "last_name": "System Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("Admin123!")
        admin.email = admin_email
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        admin.groups.add(Group.objects.get(name="Admin"))

        departments = [
            "Research Department",
            "Financial Markets Department",
            "Statistics Department",
            "Supervision Department",
            "National Payment Systems Department",
        ]
        for name in departments:
            Department.objects.get_or_create(name=name)

        self.stdout.write(self.style.SUCCESS("Seeded Django PMS development data."))
