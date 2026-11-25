import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from dbsync.codec import SYNC_MODELS, serialize_instance, sync_model
from dbsync.models import SyncEvent, SyncState
from dbsync.worker import _post_json


class Command(BaseCommand):
    help = (
        "Replace all synchronized Render app data with this local SQLite database. "
        "This is destructive and never runs automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-render-replacement",
            action="store_true",
            help="Required confirmation to replace all current Render app data.",
        )

    def handle(self, *args, **options):
        if not options["confirm_render_replacement"]:
            raise CommandError(
                "Refusing to proceed without --confirm-render-replacement."
            )
        if connection.vendor != "sqlite":
            raise CommandError("Bootstrap source must be a local SQLite database.")
        remote = urlparse(settings.DATABASE_SYNC_REMOTE_URL)
        if remote.scheme != "https" or not remote.hostname:
            raise CommandError("DATABASE_SYNC_REMOTE_URL must use HTTPS.")
        if not settings.DATABASE_SYNC_SHARED_SECRET:
            raise CommandError("DATABASE_SYNC_SHARED_SECRET is not configured.")

        count = sum(sync_model(label).objects.count() for label in SYNC_MODELS)
        if count == 0:
            raise CommandError(
                "Refusing to replace Render with an empty local database."
            )
        try:
            started = _post_json(
                "bootstrap/begin", {"count": count}
            )
            session_id = started["session"]
            batch_size = int(started["batch_size"])
            batch = []
            sequence = 0
            for label in SYNC_MODELS:
                for instance in sync_model(label).objects.order_by("pk").iterator(
                    chunk_size=500
                ):
                    batch.append(
                        {
                            "sequence": sequence,
                            "model": label,
                            "id": str(instance.sync_id),
                            "updated_at": instance.sync_updated_at.isoformat(),
                            "deleted": False,
                            "payload": serialize_instance(instance),
                        }
                    )
                    sequence += 1
                    if len(batch) == batch_size:
                        _post_json(
                            "bootstrap/upload",
                            {"session": session_id, "records": batch},
                        )
                        batch = []
            if batch:
                _post_json(
                    "bootstrap/upload", {"session": session_id, "records": batch}
                )
            result = _post_json("bootstrap/commit", {"session": session_id})
            if result.get("replaced") != count:
                raise ValueError("Bootstrap count mismatch")
        except Exception as exc:
            raise CommandError(
                "Bootstrap did not complete. Render data was not replaced unless "
                f"the final commit succeeded. Error: {exc}"
            ) from exc

        SyncEvent.objects.all().delete()
        SyncState.objects.update_or_create(
            key="remote_cursor", defaults={"value": "0"}
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Bootstrap completed: {count} local records replaced Render app data."
            )
        )
