import uuid

from django.db import models
from django.utils import timezone


class SyncModel(models.Model):
    sync_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sync_updated_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True

    def prepare_sync_save(self, kwargs):
        from .context import is_applying_remote_change

        if not is_applying_remote_change() and self._state.adding:
            identity = getattr(self, "sync_identity", None)
            natural_key = identity() if identity else None
            if natural_key is not None:
                self.sync_id = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"mam-wellbeing:{self._meta.label_lower}:{natural_key}",
                )
            elif self.sync_id is None:
                self.sync_id = uuid.uuid4()
        elif self.sync_id is None:
            self.sync_id = uuid.uuid4()
        if not is_applying_remote_change():
            self.sync_updated_at = timezone.now()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"sync_updated_at"}

    def save(self, *args, **kwargs):
        self.prepare_sync_save(kwargs)
        return super().save(*args, **kwargs)
