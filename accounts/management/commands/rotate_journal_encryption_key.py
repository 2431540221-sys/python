import os

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from accounts.crypto import fernet_for_key
from tracking.models import JournalEntry


class Command(BaseCommand):
    help = (
        "Re-encrypt every journal entry using JOURNAL_ENCRYPTION_KEY_NEXT "
        "without changing the active key setting. Can target Render via its "
        "external PostgreSQL URL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--render-database",
            action="store_true",
            help="Target the Render PostgreSQL URL in JOURNAL_ROTATION_RENDER_DATABASE_URL.",
        )
        actions = parser.add_mutually_exclusive_group(required=True)
        actions.add_argument(
            "--check-only",
            action="store_true",
            help="Verify every journal can be decrypted with the active key.",
        )
        actions.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm atomic re-encryption of all journal entries.",
        )

    def handle(self, *args, **options):
        current_key = settings.JOURNAL_ENCRYPTION_KEY
        if not current_key:
            raise CommandError("The active JOURNAL_ENCRYPTION_KEY must be set.")
        old_fernet = fernet_for_key(current_key)
        new_fernet = None
        if options["confirm"]:
            next_key = os.environ.get("JOURNAL_ENCRYPTION_KEY_NEXT", "")
            if not next_key:
                raise CommandError("JOURNAL_ENCRYPTION_KEY_NEXT must be set.")
            if current_key == next_key:
                raise CommandError(
                    "The new journal key must differ from the active key."
                )
            new_fernet = fernet_for_key(next_key)
        alias = self._database_alias(options["render_database"])
        connection = connections[alias]
        model = JournalEntry
        table = connection.ops.quote_name(model._meta.db_table)
        pk_column = connection.ops.quote_name(model._meta.pk.column)
        content_field = model._meta.get_field("content")
        content_column = connection.ops.quote_name(content_field.column)
        select_sql = (
            f"SELECT {pk_column}, {content_column} FROM {table} ORDER BY {pk_column}"
        )
        update_sql = (
            f"UPDATE {table} SET {content_column} = %s WHERE {pk_column} = %s"
        )

        rotated = 0
        with transaction.atomic(using=alias):
            with connection.cursor() as cursor:
                cursor.execute(select_sql)
                entries = cursor.fetchall()

            encrypted_entries = []
            for entry_id, ciphertext in entries:
                if not ciphertext:
                    encrypted_entries.append((ciphertext, entry_id))
                    continue
                try:
                    plaintext = old_fernet.decrypt(ciphertext.encode("ascii"))
                except (InvalidToken, UnicodeEncodeError, ValueError) as exc:
                    raise CommandError(
                        "A journal entry could not be decrypted; no entries were changed."
                    ) from exc
                if new_fernet is not None:
                    encrypted_entries.append(
                        (new_fernet.encrypt(plaintext).decode("ascii"), entry_id)
                    )
                rotated += 1

            if options["confirm"]:
                with connection.cursor() as cursor:
                    cursor.executemany(update_sql, encrypted_entries)

        if options["check_only"]:
            target = "Render " if options["render_database"] else ""
            self.stdout.write(
                self.style.SUCCESS(
                    f"{target}journal key check passed: "
                    f"{len(entries)} entries are readable."
                )
            )
        else:
            target = "Render " if options["render_database"] else ""
            self.stdout.write(
                self.style.SUCCESS(
                    f"{target}journal key rotation completed: "
                    f"{rotated} non-empty entries re-encrypted."
                )
            )

    @staticmethod
    def _database_alias(render_database):
        if not render_database:
            return "default"

        url = os.environ.get("JOURNAL_ROTATION_RENDER_DATABASE_URL", "").strip()
        if not url:
            raise CommandError(
                "Set JOURNAL_ROTATION_RENDER_DATABASE_URL to Render's external "
                "PostgreSQL URL."
            )

        import dj_database_url

        try:
            database_config = dj_database_url.parse(
                url,
                conn_max_age=0,
                ssl_require=True,
            )
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "JOURNAL_ROTATION_RENDER_DATABASE_URL is not a valid database URL."
            ) from exc
        if database_config.get("ENGINE") != "django.db.backends.postgresql":
            raise CommandError(
                "The Render rotation target must be a PostgreSQL database."
            )

        database_config = {
            **connections.databases["default"],
            **database_config,
        }
        alias = "journal_rotation_render"
        connections.databases[alias] = database_config
        return alias
