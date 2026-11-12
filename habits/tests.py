"""Task 2 - kiểm thử streak, CRUD thói quen và nhắc nhở theo giờ."""
from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from habits.models import Habit, HabitLog, Notification
from habits.services import calculate_streaks, get_habit_stats, send_due_reminders

D = date(2026, 11, 5)


def days(*offsets):
    return {D - timedelta(days=o) for o in offsets}


class StreakTests(TestCase):
    def test_empty(self):
        self.assertEqual(calculate_streaks(set(), D), (0, 0))

    def test_seven_consecutive_days(self):
        self.assertEqual(calculate_streaks(days(*range(0, 7)), D), (7, 7))

    def test_streak_alive_if_yesterday_done_today_not_yet(self):
        self.assertEqual(calculate_streaks(days(*range(1, 8)), D), (7, 7))

    def test_skip_a_day_resets_current_streak_to_zero(self):
        # đã làm 7 ngày liên tiếp, rồi bỏ cả hôm qua lẫn hôm nay -> chuỗi hiện tại về 0, dài nhất vẫn là 7
        self.assertEqual(calculate_streaks(days(*range(2, 9)), D), (0, 7))

    def test_after_gap_streak_restarts_at_one(self):
        self.assertEqual(calculate_streaks(days(0, *range(2, 9)), D), (1, 7))

    def test_longest_streak_tracked_separately(self):
        self.assertEqual(calculate_streaks(days(0, 1, 5, 6, 7, 8), D), (2, 4))

    def test_future_dates_ignored(self):
        self.assertEqual(calculate_streaks({D + timedelta(days=1)}, D), (0, 0))


class HabitFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a", password="Matkhau!2026x")
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})

    def test_crud(self):
        r = self.client.post(reverse("habit_create"), {"name": "Đọc sách", "weekly_target": 5, "streak_goal": 21})
        habit = Habit.objects.get(user=self.user)
        self.assertRedirects(r, reverse("habit_detail", args=[habit.pk]))
        self.client.post(reverse("habit_update", args=[habit.pk]), {"name": "Đọc sách 15p", "weekly_target": 6})
        habit.refresh_from_db()
        self.assertEqual((habit.name, habit.weekly_target), ("Đọc sách 15p", 6))
        self.client.post(reverse("habit_delete", args=[habit.pk]))
        self.assertFalse(Habit.objects.exists())

    def test_reminder_needs_time(self):
        r = self.client.post(reverse("habit_create"), {"name": "X", "weekly_target": 7, "reminder_enabled": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Habit.objects.exists())

    def test_tick_seven_days_in_a_row_increases_streak(self):
        """Demo thầy yêu cầu: tick hoàn thành 7 ngày liên tiếp thì streak tăng dần.
        (Chuỗi tính lùi từ hôm nay, nên tick hôm nay trước rồi lùi dần về các ngày trước.)"""
        habit = Habit.objects.create(user=self.user, name="Đi bộ")
        today = timezone.localdate()
        for i in range(1, 8):
            self.client.post(reverse("habit_toggle", args=[habit.pk]), {"date": (today - timedelta(days=i - 1)).isoformat()})
            self.assertEqual(get_habit_stats(habit)["current_streak"], i)

    def test_skip_a_day_then_streak_is_zero(self):
        """Demo thầy yêu cầu: bỏ 1 ngày thì streak về 0."""
        habit = Habit.objects.create(user=self.user, name="Đi bộ")
        today = timezone.localdate()
        for offset in range(2, 9):
            HabitLog.objects.create(habit=habit, date=today - timedelta(days=offset))
        self.assertEqual(get_habit_stats(habit)["current_streak"], 0)
        self.assertEqual(get_habit_stats(habit)["longest_streak"], 7)

    def test_toggle_twice_unmarks(self):
        habit = Habit.objects.create(user=self.user, name="Đi bộ")
        self.client.post(reverse("habit_toggle", args=[habit.pk]))
        self.assertEqual(habit.logs.count(), 1)
        self.client.post(reverse("habit_toggle", args=[habit.pk]))
        self.assertEqual(habit.logs.count(), 0)

    def test_cannot_mark_future_day(self):
        habit = Habit.objects.create(user=self.user, name="Đi bộ")
        self.client.post(reverse("habit_toggle", args=[habit.pk]), {"date": (timezone.localdate() + timedelta(days=1)).isoformat()})
        self.assertEqual(habit.logs.count(), 0)


class ReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a", password="Matkhau!2026x")

    def now_at(self, hour, minute=0):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(hour, minute)))

    def test_reminder_sent_once_when_due(self):
        Habit.objects.create(user=self.user, name="Uống nước", reminder_enabled=True, reminder_time=time(8, 0))
        self.assertEqual(send_due_reminders(self.now_at(7, 59)), 0)       # chưa tới giờ
        self.assertEqual(send_due_reminders(self.now_at(8, 1)), 1)        # tới giờ
        self.assertEqual(send_due_reminders(self.now_at(8, 5)), 0)        # không nhắc lần 2 trong ngày
        self.assertEqual(Notification.objects.filter(kind="reminder").count(), 1)

    def test_no_reminder_if_already_done_today(self):
        habit = Habit.objects.create(user=self.user, name="Uống nước", reminder_enabled=True, reminder_time=time(8, 0))
        HabitLog.objects.create(habit=habit, date=timezone.localdate())
        self.assertEqual(send_due_reminders(self.now_at(9)), 0)

    def test_disabled_reminder_not_sent(self):
        Habit.objects.create(user=self.user, name="X", reminder_enabled=False, reminder_time=time(8, 0))
        self.assertEqual(send_due_reminders(self.now_at(9)), 0)
