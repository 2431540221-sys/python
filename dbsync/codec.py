from datetime import date, datetime, time

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from accounts.crypto import DECRYPT_FAILED, decrypt_text, encrypt_text
from accounts.models import User

from .context import applying_remote_change, reset_applying_remote_change
from .models import SyncEvent, SyncTombstone


def event_json(event):
    return {
        "model": event.model_label,
        "id": str(event.object_id),
        "updated_at": event.updated_at.isoformat(),
        "deleted": event.deleted,
        "payload": event.payload,
    }


SYNC_MODELS = (
    "accounts.user",
    "habits.habit",
    "habits.habitlog",
    "habits.notification",
    "habits.browserpushsubscription",
    "tracking.dailycheckin",
    "tracking.journalentry",
    "coach.coachreport",
    "insights.dailywellbeingindex",
)


def sync_model(label):
    if label not in SYNC_MODELS:
        raise ValueError("Unsupported synchronized model")
    return apps.get_model(label)


def serialize_instance(instance):
    payload = {}
    references = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in {"sync_id", "sync_updated_at"}:
            continue
        if field.many_to_one:
            related = getattr(instance, field.name)
            references[field.name] = str(related.sync_id) if related else None
            continue
        value = getattr(instance, field.attname)
        if instance._meta.label_lower == "tracking.journalentry" and field.name == "content":
            if value == DECRYPT_FAILED:
                raise ValueError("A local journal entry could not be decrypted")
            value = encrypt_text(value) if value else value
        elif isinstance(value, (date, datetime, time)):
            value = value.isoformat()
        payload[field.name] = value
    payload["_references"] = references
    if isinstance(instance, User):
        payload["_groups"] = list(instance.groups.values_list("name", flat=True))
        payload["_permissions"] = list(
            instance.user_permissions.values_list(
                "content_type__app_label", "codename"
            )
        )
    return payload


def append_event(model_label, object_id, updated_at, deleted, payload=None):
    SyncEvent.objects.create(
        model_label=model_label,
        object_id=object_id,
        updated_at=updated_at,
        deleted=deleted,
        payload=payload,
    )


def _coerce(field, value):
    if value is None:
        return None
    if field.get_internal_type() == "DateTimeField":
        return parse_datetime(value) if isinstance(value, str) else value
    if field.get_internal_type() == "DateField":
        return parse_date(value) if isinstance(value, str) else value
    if field.get_internal_type() == "TimeField":
        return parse_time(value) if isinstance(value, str) else value
    return field.to_python(value)


def _set_user_memberships(user, payload):
    if "_groups" in payload:
        groups = [Group.objects.get_or_create(name=name)[0] for name in payload["_groups"]]
        user.groups.set(groups)
    if "_permissions" in payload:
        permissions = []
        for app_label, codename in payload["_permissions"]:
            try:
                permissions.append(
                    Permission.objects.get(
                        content_type__app_label=app_label, codename=codename
                    )
                )
            except Permission.DoesNotExist as exc:
                raise ValueError("A synchronized account permission is unavailable") from exc
        user.user_permissions.set(permissions)


@transaction.atomic
def apply_record(model_label, object_id, updated_at, deleted, payload):
    model = sync_model(model_label)
    if isinstance(updated_at, str):
        updated_at = parse_datetime(updated_at)
    if updated_at is None or updated_at.tzinfo is None:
        raise ValueError("Synchronization timestamps must include a timezone")
    existing = model.objects.filter(sync_id=object_id).first()
    tombstone = SyncTombstone.objects.filter(
        model_label=model_label, object_id=object_id
    ).first()
    newest = max(
        (value for value in (
            existing.sync_updated_at if existing else None,
            tombstone.updated_at if tombstone else None,
        ) if value is not None),
        default=None,
    )
    if newest is not None and updated_at <= newest:
        return False

    token = applying_remote_change()
    try:
        if deleted:
            if existing is not None:
                existing.delete()
            SyncTombstone.objects.update_or_create(
                model_label=model_label,
                object_id=object_id,
                defaults={"updated_at": updated_at},
            )
            return True

        if not isinstance(payload, dict):
            raise ValueError("Synchronization payload must be an object")
        instance = existing or model()
        references = payload.get("_references", {})
        if not isinstance(references, dict):
            raise ValueError("Invalid synchronized references")
        allowed = {
            field.name: field
            for field in model._meta.concrete_fields
            if not field.primary_key and field.name not in {"sync_id", "sync_updated_at"}
        }
        unknown = set(payload) - set(allowed) - {"_references", "_groups", "_permissions"}
        if unknown:
            raise ValueError("Synchronization payload has unsupported fields")
        for name, value in payload.items():
            if name in allowed:
                setattr(instance, allowed[name].attname, _coerce(allowed[name], value))
        for name, reference_id in references.items():
            field = allowed.get(name)
            if field is None or not field.many_to_one:
                raise ValueError("Synchronization payload has an invalid reference")
            if reference_id is None:
                setattr(instance, field.name, None)
            else:
                related = field.remote_field.model.objects.filter(sync_id=reference_id).first()
                if related is None:
                    raise ValueError("A synchronized parent record is missing")
                setattr(instance, field.name, related)
        if model_label == "tracking.journalentry":
            encrypted = payload.get("content")
            if encrypted:
                plaintext = decrypt_text(encrypted)
                if plaintext == DECRYPT_FAILED:
                    raise ValueError("Journal encryption keys do not match")
                instance.content = plaintext
        instance.sync_id = object_id
        instance.sync_updated_at = updated_at
        instance.save()
        if isinstance(instance, User):
            _set_user_memberships(instance, payload)
        SyncTombstone.objects.filter(model_label=model_label, object_id=object_id).delete()
        return True
    except (ValidationError, TypeError) as exc:
        raise ValueError("Invalid synchronized record") from exc
    finally:
        reset_applying_remote_change(token)
