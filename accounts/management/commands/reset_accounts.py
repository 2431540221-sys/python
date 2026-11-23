import os

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all accounts and related data, then create one user and one admin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion of all accounts and related data.",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("This deletes all accounts and related data. Add --confirm to continue.")

        user_password = os.environ.get("ACCOUNT_USER_PASSWORD")
        admin_password = os.environ.get("ACCOUNT_ADMIN_PASSWORD")
        if not user_password or not admin_password:
            raise CommandError("Set ACCOUNT_USER_PASSWORD and ACCOUNT_ADMIN_PASSWORD in the environment.")
        if user_password == admin_password:
            raise CommandError("The user and admin passwords must be different.")

        User = get_user_model()
        with transaction.atomic():
            User.objects.all().delete()
            Session.objects.all().delete()
            User.objects.create_user(
                username="nguyenvana",
                password=user_password,
                role=User.ROLE_USER,
            )
            User.objects.create_superuser(
                username="thaoquyen",
                password=admin_password,
            )

        self.stdout.write(self.style.SUCCESS("Created one user and one admin account."))
