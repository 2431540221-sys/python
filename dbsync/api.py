import hmac
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils.dateparse import parse_datetime
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from .codec import SYNC_MODELS, apply_record, event_json, sync_model
from .context import applying_remote_change, reset_applying_remote_change
from .models import (
    SyncBootstrapRow,
    SyncBootstrapSession,
    SyncEvent,
    SyncState,
    SyncTombstone,
)

router = APIRouter(prefix="/internal/sync")
MAX_BATCH = 200
MAX_BOOTSTRAP_BATCH = 25
MAX_BOOTSTRAP_RECORDS = 1_000_000

logger = logging.getLogger(__name__)


def _authorized(request):
    expected = settings.DATABASE_SYNC_SHARED_SECRET
    supplied = request.headers.get("x-database-sync-secret", "")
    if not expected:
        reason = "server_secret_unset"
    elif not supplied:
        reason = "header_missing"
    elif not hmac.compare_digest(supplied, expected):
        reason = "secret_mismatch"
    else:
        return True

    logger.warning(
        "Database sync authorization rejected: reason=%s server_secret_length=%d "
        "request_header_length=%d",
        reason,
        len(expected),
        len(supplied),
    )
    return False


def _unauthorized():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _parse_event(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid synchronization event")
    label = data.get("model")
    if label not in SYNC_MODELS:
        raise ValueError("Unsupported synchronized model")
    object_id = uuid.UUID(str(data.get("id")))
    timestamp = parse_datetime(data.get("updated_at", ""))
    if timestamp is None or timestamp.tzinfo is None:
        raise ValueError("Invalid synchronization timestamp")
    deleted = data.get("deleted")
    if not isinstance(deleted, bool):
        raise ValueError("Invalid synchronization operation")
    return label, object_id, timestamp, deleted, data.get("payload")


@router.post("/exchange/")
def exchange(request: Request, body: dict = Body(...)):
    if not _authorized(request):
        return _unauthorized()
    try:
        after = int(body.get("after", 0))
        acknowledged = int(body.get("acknowledged", 0))
        incoming = body.get("changes", [])
        if after < 0 or acknowledged < 0 or not isinstance(incoming, list):
            raise ValueError("Invalid synchronization cursor")
        if len(incoming) > MAX_BATCH:
            raise ValueError("Synchronization batch is too large")
        with transaction.atomic():
            if acknowledged:
                SyncEvent.objects.filter(pk__lte=acknowledged).delete()
            for item in incoming:
                label, object_id, timestamp, deleted, payload = _parse_event(item)
                apply_record(label, object_id, timestamp, deleted, payload)
            events = list(
                SyncEvent.objects.filter(pk__gt=after).order_by("pk")[:MAX_BATCH]
            )
            next_cursor = events[-1].pk if events else after
            response = {
                "changes": [event_json(event) for event in events],
                "cursor": next_cursor,
            }
        return response
    except (ValueError, TypeError, KeyError):
        return JSONResponse({"error": "invalid_sync_request"}, status_code=400)


@router.post("/bootstrap/begin/")
def bootstrap_begin(request: Request, body: dict = Body(...)):
    if not _authorized(request):
        return _unauthorized()
    try:
        count = int(body.get("count"))
        if count <= 0 or count > MAX_BOOTSTRAP_RECORDS:
            raise ValueError
        session = SyncBootstrapSession.objects.create(expected_count=count)
        return {"session": str(session.pk), "batch_size": MAX_BOOTSTRAP_BATCH}
    except (ValueError, TypeError, KeyError):
        return JSONResponse({"error": "invalid_bootstrap_request"}, status_code=400)


@router.post("/bootstrap/upload/")
def bootstrap_upload(request: Request, body: dict = Body(...)):
    if not _authorized(request):
        return _unauthorized()
    try:
        session = SyncBootstrapSession.objects.get(pk=uuid.UUID(str(body.get("session"))))
        records = body.get("records")
        if not isinstance(records, list) or not 1 <= len(records) <= MAX_BOOTSTRAP_BATCH:
            raise ValueError
        rows = []
        for record in records:
            label, object_id, timestamp, deleted, payload = _parse_event(record)
            if deleted or not isinstance(payload, dict):
                raise ValueError
            sequence = int(record.get("sequence"))
            if sequence < 0 or sequence >= session.expected_count:
                raise ValueError
            rows.append(
                SyncBootstrapRow(
                    session=session,
                    sequence=sequence,
                    model_label=label,
                    object_id=object_id,
                    updated_at=timestamp,
                    payload=payload,
                )
            )
        with transaction.atomic():
            SyncBootstrapRow.objects.bulk_create(rows)
        return {"uploaded": len(rows)}
    except (ValueError, TypeError, KeyError, SyncBootstrapSession.DoesNotExist):
        return JSONResponse({"error": "invalid_bootstrap_request"}, status_code=400)


@router.post("/bootstrap/commit/")
def bootstrap_commit(request: Request, body: dict = Body(...)):
    if not _authorized(request):
        return _unauthorized()
    try:
        session_id = uuid.UUID(str(body.get("session")))
        with transaction.atomic():
            session = SyncBootstrapSession.objects.select_for_update().get(pk=session_id)
            rows = session.rows.order_by("sequence")
            count = rows.count()
            sequence_range = rows.aggregate(first=Max("sequence"))
            if count != session.expected_count or (
                count and sequence_range["first"] != count - 1
            ):
                return JSONResponse({"error": "incomplete_bootstrap"}, status_code=409)

            token = applying_remote_change()
            try:
                for label in reversed(SYNC_MODELS):
                    sync_model(label).objects.all().delete()
                SyncTombstone.objects.all().delete()
                SyncEvent.objects.all().delete()
                SyncState.objects.all().delete()
                for row in rows.iterator(chunk_size=500):
                    apply_record(
                        row.model_label,
                        row.object_id,
                        row.updated_at,
                        False,
                        row.payload,
                    )
            finally:
                reset_applying_remote_change(token)
            session.delete()
        return {"replaced": count}
    except (ValueError, TypeError, KeyError, SyncBootstrapSession.DoesNotExist):
        return JSONResponse({"error": "invalid_bootstrap_request"}, status_code=400)
