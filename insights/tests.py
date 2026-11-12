"""Task 4 - kiểm thử API tổng hợp tuần/tháng, dashboard và thông báo sắp mất streak."""
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.demo import seed_user_data
from accounts.models import User
from accounts.tokens import create_access_token
from habits.models import Habit, HabitLog, Notification
from insights.services import create_streak_risk_notifications, period_stats


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
        self.assertEqual(create_streak_risk_notifications(self.at(10)), 0)    # còn sớm
        self.assertEqual(create_streak_risk_notifications(self.at(19)), 1)
        n = Notification.objects.get(kind="streak_risk")
        self.assertIn("5 ngày", n.title)
        self.assertEqual(create_streak_risk_notifications(self.at(20)), 0)    # chỉ báo 1 lần/ngày

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
