"""Task 4 - kiểm thử API tổng hợp tuần/tháng, dashboard và thông báo sắp mất streak."""
import json
import random
from datetime import datetime, time, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core import mail

from accounts.demo import seed_user_data
from accounts.models import User
from accounts.tokens import create_access_token
from habits.models import BrowserPushSubscription, Habit, HabitLog, Notification
from insights.services import (
    create_streak_risk_notifications, create_wellbeing_trend_notifications, period_stats,
)
from insights.models import DailyWellbeingIndex
from tracking.models import DailyCheckin


def bearer(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


class StatsTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("a", password="Matkhau!2026x")
        self.b = User.objects.create_user("b", password="Matkhau!2026x")
        seed_user_data(self.a, 30)

    def test_week_and_month_series(self):
        week = self.client.get("/api/stats/?period=week", **bearer(self.a)).json()
        month = self.client.get("/api/stats/?period=month", **bearer(self.a)).json()
        self.assertEqual(len(week["daily"]), 7)
        self.assertEqual(len(month["daily"]), 30)
        self.assertEqual(len(month["weekly"]), 5)             # 30 ngày = 4 khối 7 ngày + khối 2 ngày
        self.assertEqual(month["summary"]["checkin_days"], 30)
        self.assertIsNotNone(month["summary"]["avg_mood"])
        self.assertTrue(1 <= month["summary"]["avg_mood"] <= 5)

    def test_invalid_period(self):
        self.assertEqual(self.client.get("/api/stats/?period=year", **bearer(self.a)).status_code, 400)

    def test_stats_are_scoped_to_user(self):
        data = self.client.get("/api/stats/?period=month", **bearer(self.b)).json()
        self.assertEqual(data["summary"]["checkin_days"], 0)
        self.assertEqual(data["summary"]["habits_done"], 0)

    def test_needs_login(self):
        self.assertEqual(self.client.get("/api/stats/").status_code, 401)

    def test_dashboard_renders_with_30_days_of_data(self):
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="chart-index"')
        self.assertContains(r, 'id="chart-mood"')
        self.assertContains(r, 'id="chart-habits"')
        # cookie JWT gọi được API chỉ-đọc để vẽ biểu đồ
        self.assertEqual(self.client.get("/api/stats/?period=month").status_code, 200)

    def test_completion_percent(self):
        habit = Habit.objects.create(user=self.b, name="X")
        today = timezone.localdate()
        for i in range(7):
            HabitLog.objects.create(habit=habit, date=today - timedelta(days=i))
        s = period_stats(self.b, "week")["summary"]
        self.assertEqual(s["completion_percent"], 100)
        self.assertEqual(s["best_current_streak"], 7)

    def test_wellbeing_index_is_stored_and_reported(self):
        today = timezone.localdate()
        Habit.objects.create(user=self.a, name="Đi bộ")
        DailyCheckin.objects.update_or_create(
            user=self.a,
            date=today,
            defaults={"mood": 5, "sleep_hours": 8, "activity_minutes": 30},
        )

        data = period_stats(self.a, "week")

        stored = DailyWellbeingIndex.objects.get(user=self.a, date=today)
        self.assertIsNotNone(stored.score)
        self.assertEqual(stored.mood_score, 100)
        self.assertEqual(stored.coverage_percent, 100)
        self.assertEqual(data["daily"][-1]["wellbeing_index"], stored.score)
        self.assertIsNotNone(data["summary"]["avg_wellbeing_index"])

    def test_wellbeing_index_is_refreshed_when_source_changes(self):
        today = timezone.localdate()
        checkin, _ = DailyCheckin.objects.update_or_create(
            user=self.a,
            date=today,
            defaults={"mood": 1, "sleep_hours": 8, "activity_minutes": 30},
        )
        period_stats(self.a, "week")
        checkin.mood = 5
        checkin.save()

        data = period_stats(self.a, "week")

        self.assertEqual(data["daily"][-1]["index_mood"], 100)

    def test_wellbeing_index_is_not_rewritten_when_sources_are_unchanged(self):
        period_stats(self.a, "week")
        today = timezone.localdate()
        sentinel = timezone.now() - timedelta(days=1)
        DailyWellbeingIndex.objects.filter(user=self.a, date=today).update(updated_at=sentinel)

        period_stats(self.a, "week")

        self.assertEqual(
            DailyWellbeingIndex.objects.get(user=self.a, date=today).updated_at,
            sentinel,
        )

    def test_missing_checkin_is_not_recorded_as_a_zero_wellbeing_score(self):
        Habit.objects.create(user=self.b, name="Đi bộ")

        data = period_stats(self.b, "week")
        index = DailyWellbeingIndex.objects.get(user=self.b, date=timezone.localdate())

        self.assertIsNone(index.score)
        self.assertEqual(index.coverage_percent, 30)
        self.assertIsNone(data["daily"][-1]["wellbeing_index"])


class StreakRiskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a", password="Matkhau!2026x")
        self.habit = Habit.objects.create(user=self.user, name="Đọc sách")
        today = timezone.localdate()
        for i in range(1, 6):         # chuỗi 5 ngày kết thúc hôm qua, hôm nay chưa làm
            HabitLog.objects.create(habit=self.habit, date=today - timedelta(days=i))

    def at(self, hour):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(hour, 0)))

    def test_notifies_when_streak_about_to_break(self):
        self.user.email = "a@example.com"
        self.user.save(update_fields=["email"])
        self.assertEqual(create_streak_risk_notifications(self.at(10)), 0)    # còn sớm
        self.assertEqual(create_streak_risk_notifications(self.at(19)), 1)
        n = Notification.objects.get(kind="streak_risk")
        self.assertIn("5 ngày", n.title)
        self.assertEqual(create_streak_risk_notifications(self.at(20)), 0)    # chỉ báo 1 lần/ngày
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["a@example.com"])

    def test_no_notification_if_done_today(self):
        HabitLog.objects.create(habit=self.habit, date=timezone.localdate())
        self.assertEqual(create_streak_risk_notifications(self.at(19)), 0)

    def test_no_notification_without_streak(self):
        HabitLog.objects.all().delete()
        self.assertEqual(create_streak_risk_notifications(self.at(19)), 0)

    def test_notifications_page_and_mark_read(self):
        create_streak_risk_notifications(self.at(19))
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})
        self.assertContains(self.client.get(reverse("notifications")), "Sắp mất chuỗi")
        self.client.post(reverse("notifications_read"))
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)


class WellbeingTrendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("trend", password="Matkhau!2026x")
        self.today = timezone.localdate()
        rng = random.Random(20261124)
        for offset in range(14):
            recent = offset < 7
            mood = rng.randint(1, 2) if recent else rng.randint(4, 5)
            sleep = round(rng.uniform(5.2, 6.2) if recent else rng.uniform(7.2, 8.5), 1)
            minutes = rng.randint(0, 20) if recent else rng.randint(30, 60)
            DailyCheckin.objects.create(
                user=self.user, date=self.today - timedelta(days=offset),
                mood=mood, sleep_hours=sleep,
                activity_type="walking" if minutes else "none", activity_minutes=minutes,
            )

    def test_sends_one_supportive_nudge_for_clear_decline(self):
        now = timezone.make_aware(datetime.combine(self.today, time(20, 0)))

        self.assertEqual(create_wellbeing_trend_notifications(now, self.user), 1)
        self.assertEqual(create_wellbeing_trend_notifications(now, self.user), 0)
        notification = Notification.objects.get(kind=Notification.KIND_WELLBEING)
        self.assertIn("không phải đánh giá y tế", notification.body)
        indices = list(DailyWellbeingIndex.objects.filter(user=self.user))
        self.assertEqual(len(indices), 14)
        self.assertTrue(all(index.score is not None for index in indices))
        self.assertTrue(all(index.coverage_percent == 70 for index in indices))

    def test_does_not_nudge_without_enough_checkins(self):
        DailyCheckin.objects.filter(user=self.user, date__gte=self.today - timedelta(days=6)).delete()
        now = timezone.make_aware(datetime.combine(self.today, time(20, 0)))

        self.assertEqual(create_wellbeing_trend_notifications(now, self.user), 0)
        self.assertFalse(Notification.objects.filter(kind=Notification.KIND_WELLBEING).exists())


class PushSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("pushuser", password="Matkhau!2026x")
        self.client.force_login(self.user)
        self.url = reverse("push_subscription")
        self.subscription = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/example",
            "keys": {"p256dh": "public-key", "auth": "auth-secret"},
        }

    @override_settings(VAPID_PUBLIC_KEY="public", VAPID_PRIVATE_KEY="private")
    def test_registers_and_removes_browser_subscription(self):
        response = self.client.post(
            self.url, json.dumps(self.subscription), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(BrowserPushSubscription.objects.filter(user=self.user).exists())

        response = self.client.delete(
            self.url,
            json.dumps({"endpoint": self.subscription["endpoint"]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BrowserPushSubscription.objects.filter(user=self.user).exists())

    @override_settings(VAPID_PUBLIC_KEY="public", VAPID_PRIVATE_KEY="private")
    def test_rejects_non_https_push_endpoint(self):
        subscription = {**self.subscription, "endpoint": "http://127.0.0.1/internal"}
        response = self.client.post(self.url, json.dumps(subscription), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_service_worker_is_available_at_root_scope(self):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
