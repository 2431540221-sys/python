from django.db.models.signals import m2m_changed, post_delete, post_save
from django.utils import timezone

from .codec import SYNC_MODELS, append_event, serialize_instance
from .context import is_applying_remote_change
from .models import SyncTombstone

_registered = False


def _tracked(sender):
    return sender._meta.label_lower in SYNC_MODELS


def _saved(sender, instance, raw=False, **kwargs):
    if raw or is_applying_remote_change() or not _tracked(sender):
        return
    append_event(
        sender._meta.label_lower,
        instance.sync_id,
        instance.sync_updated_at,
        False,
        serialize_instance(instance),
    )


def _deleted(sender, instance, **kwargs):
    if is_applying_remote_change() or not _tracked(sender):
        return
    deleted_at = timezone.now()
    SyncTombstone.objects.update_or_create(
        model_label=sender._meta.label_lower,
        object_id=instance.sync_id,
        defaults={"updated_at": deleted_at},
    )
    append_event(
        sender._meta.label_lower, instance.sync_id, deleted_at, True
    )


def _membership_changed(sender, instance, action, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if not is_applying_remote_change() and _tracked(instance.__class__):
        instance.save(update_fields=["sync_updated_at"])


def register():
    global _registered
    if _registered:
        return
    post_save.connect(_saved, dispatch_uid="dbsync_post_save", weak=False)
    post_delete.connect(_deleted, dispatch_uid="dbsync_post_delete", weak=False)
    m2m_changed.connect(
        _membership_changed,
        sender=None,
        dispatch_uid="dbsync_user_memberships",
        weak=False,
    )
    _registered = True
