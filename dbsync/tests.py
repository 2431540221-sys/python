import uuid
from datetime import timedelta

from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from fastapi.testclient import TestClient

from accounts.models import User
from habits.models import Habit, HabitLog
from tracking.models import JournalEntry

from .base import SyncModel
from .codec import apply_record, serialize_instance
from .models import SyncEvent


class SyncCodecTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sync-owner",
            password="test-password",
        )
        SyncEvent.objects.all().delete()

    def test_latest_update_wins_and_remote_changes_are_not_requeued(self):
        payload = serialize_instance(self.user)
        newest = timezone.now() + timedelta(seconds=2)
        payload["username"] = "updated-owner"

        self.assertTrue(
            apply_record(
                "accounts.user", self.user.sync_id, newest, False, payload
            )
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "updated-owner")
        self.assertEqual(self.user.sync_updated_at, newest)
        self.assertFalse(SyncEvent.objects.exists())

        payload["username"] = "stale-owner"
        self.assertFalse(
            apply_record(
                "accounts.user",
                self.user.sync_id,
                newest - timedelta(seconds=1),
                False,
                payload,
            )
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "updated-owner")

    def test_tombstone_prevents_stale_record_resurrection(self):
        payload = serialize_instance(self.user)
        object_id = self.user.sync_id
        deleted_at = timezone.now() + timedelta(seconds=2)

        self.assertTrue(
            apply_record(
                "accounts.user", object_id, deleted_at, True, None
            )
        )
        self.assertFalse(
            apply_record(
                "accounts.user",
                object_id,
                deleted_at - timedelta(seconds=1),
                False,
                payload,
            )
        )
        self.assertFalse(User.objects.filter(sync_id=object_id).exists())

    def test_new_habit_logs_share_identity_for_same_habit_and_date(self):
        habit = Habit.objects.create(user=self.user, name="Walk")
        day = timezone.localdate()
        first = HabitLog(habit=habit, date=day)
        second = HabitLog(habit=habit, date=day)

        SyncModel.prepare_sync_save(first, {})
        SyncModel.prepare_sync_save(second, {})

        self.assertEqual(first.sync_id, second.sync_id)

    def test_journal_payload_is_encrypted_and_can_be_applied(self):
        plaintext = "private journal text"
        journal = JournalEntry.objects.create(
            user=self.user,
            title="Private",
            content=plaintext,
        )
        payload = serialize_instance(journal)

        self.assertNotIn(plaintext, payload["content"])
        copied_id = uuid.uuid4()
        copied_at = timezone.now() + timedelta(seconds=2)
        self.assertTrue(
            apply_record(
                "tracking.journalentry",
                copied_id,
                copied_at,
                False,
                payload,
            )
        )
        self.assertEqual(
            JournalEntry.objects.get(sync_id=copied_id).content,
            plaintext,
        )


class SyncApiTests(TransactionTestCase):
    @override_settings(DATABASE_SYNC_SHARED_SECRET="test-sync-secret")
    def test_exchange_requires_secret_and_reads_events(self):
        from coach_service.api import api_app

        with TestClient(api_app) as client:
            denied = client.post(
                "/internal/sync/exchange/",
                json={"after": 0, "acknowledged": 0, "changes": []},
            )
            with self.assertLogs("dbsync.api", level="WARNING") as auth_logs:
                mismatch = client.post(
                    "/internal/sync/exchange/",
                    json={"after": 0, "acknowledged": 0, "changes": []},
                    headers={"X-Database-Sync-Secret": "incorrect"},
                )
            empty_bootstrap = client.post(
                "/internal/sync/bootstrap/begin/",
                json={"count": 0},
                headers={"X-Database-Sync-Secret": "test-sync-secret"},
            )
            accepted = client.post(
                "/internal/sync/exchange/",
                json={"after": 0, "acknowledged": 0, "changes": []},
                headers={"X-Database-Sync-Secret": "test-sync-secret"},
            )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(mismatch.status_code, 401)
        self.assertIn("secret_mismatch", auth_logs.output[0])
        self.assertNotIn("test-sync-secret", auth_logs.output[0])
        self.assertEqual(empty_bootstrap.status_code, 400)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json(), {"changes": [], "cursor": 0})
