import json
import logging
import os
import sys
import threading
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.db import close_old_connections, transaction

from .codec import apply_record, event_json
from .models import SyncEvent, SyncState

logger = logging.getLogger(__name__)


def _remote_endpoint(suffix):
    base = settings.DATABASE_SYNC_REMOTE_URL
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("The synchronization endpoint must use HTTPS")
    if not settings.DATABASE_SYNC_SHARED_SECRET:
        raise ValueError("Database synchronization secret is not configured")
    return f"{base}/internal/sync/{suffix}/"


def _post_json(suffix, payload):
    request = urllib.request.Request(
        _remote_endpoint(suffix),
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Database-Sync-Secret": settings.DATABASE_SYNC_SHARED_SECRET,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise OSError("Synchronization endpoint returned an error")
        return json.loads(response.read().decode("utf-8"))


def _state_value(key):
    row = SyncState.objects.filter(pk=key).first()
    return int(row.value) if row else 0


def _set_state(key, value):
    SyncState.objects.update_or_create(key=key, defaults={"value": str(value)})


def synchronize_once():
    close_old_connections()
    try:
        outgoing = list(SyncEvent.objects.order_by("pk")[:200])
        local_cursor = outgoing[-1].pk if outgoing else 0
        after = _state_value("remote_cursor")
        changes = [event_json(event) for event in outgoing]
        result = _post_json(
            "exchange",
            {
                "after": after,
                "acknowledged": after,
                "changes": changes,
            },
        )
        incoming = result.get("changes", [])
        cursor = int(result.get("cursor", after))
        if cursor < after or not isinstance(incoming, list):
            raise ValueError("Invalid synchronization response")
        with transaction.atomic():
            for change in incoming:
                apply_record(
                    change["model"],
                    change["id"],
                    change["updated_at"],
                    change["deleted"],
                    change.get("payload"),
                )
            if local_cursor:
                SyncEvent.objects.filter(pk__lte=local_cursor).delete()
            _set_state("remote_cursor", cursor)
    finally:
        close_old_connections()


def _try_process_lock():
    lock_path = settings.BASE_DIR / ".database-sync-worker.lock"
    handle = open(lock_path, "a+b")
    try:
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            if os.path.getsize(lock_path) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _run_worker(lock_handle):
    interval = settings.DATABASE_SYNC_INTERVAL_SECONDS
    delay = interval
    while True:
        time.sleep(delay)
        try:
            synchronize_once()
            delay = interval
        except Exception:
            logger.exception("Database synchronization attempt failed")
            delay = min(max(interval, delay * 2), 900)
    # Keep the process lock alive for this worker's lifetime.
    _ = lock_handle


def start_worker_if_configured():
    if not settings.DATABASE_SYNC_ENABLED:
        return
    if not settings.DATABASE_SYNC_SHARED_SECRET or not settings.DATABASE_SYNC_REMOTE_URL:
        logger.warning("Database synchronization is enabled but is not fully configured")
        return
    try:
        lock_handle = _try_process_lock()
    except OSError:
        logger.warning("Database synchronization worker lock could not be acquired")
        return
    if lock_handle is None:
        return
    thread = threading.Thread(
        target=_run_worker,
        args=(lock_handle,),
        name="database-sync",
        daemon=True,
    )
    thread.start()
