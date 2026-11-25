import uuid

from django.db import models
from django.utils import timezone


class SyncEvent(models.Model):
    model_label = models.CharField(max_length=100)
    object_id = models.UUIDField()
    updated_at = models.DateTimeField()
    deleted = models.BooleanField(default=False)
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["pk"]
        indexes = [models.Index(fields=["model_label", "object_id"])]


class SyncTombstone(models.Model):
    model_label = models.CharField(max_length=100)
    object_id = models.UUIDField()
    updated_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["model_label", "object_id"], name="dbsync_one_tombstone"
            )
        ]


class SyncState(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    value = models.CharField(max_length=200)


class SyncBootstrapSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expected_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)


class SyncBootstrapRow(models.Model):
    session = models.ForeignKey(
        SyncBootstrapSession, on_delete=models.CASCADE, related_name="rows"
    )
    sequence = models.PositiveIntegerField()
    model_label = models.CharField(max_length=100)
    object_id = models.UUIDField()
    updated_at = models.DateTimeField()
    payload = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "sequence"], name="dbsync_unique_bootstrap_sequence"
            )
        ]
