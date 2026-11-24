"""Task 3 - kiểm thử check-in (mood 1-5, giờ ngủ, hoạt động) và journal riêng tư."""
import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.sample_data import seed_user_data
from accounts.models import User
from accounts.tokens import create_access_token
from tracking.models import DailyCheckin, JournalEntry


class CheckinTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a", password="Matkhau!2026x")
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})
        self.today = timezone.localdate()

    def payload(self, **kw):
        data = {"date": self.today.isoformat(), "mood": 4, "sleep_hours": 7.5,
                "activity_type": "walking", "activity_minutes": 30, "note": ""}
        data.update(kw)
        return data

    def test_valid_checkin_saved(self):
        r = self.client.post(reverse("checkin"), self.payload())
        self.assertRedirects(r, reverse("history"))
        c = DailyCheckin.objects.get(user=self.user)
        self.assertEqual((c.mood, c.sleep_hours, c.activity_type, c.activity_minutes), (4, 7.5, "walking", 30))

    def test_mood_must_be_1_to_5(self):
        for bad in (0, 6, 10):
            self.client.post(reverse("checkin"), self.payload(mood=bad))
        self.assertFalse(DailyCheckin.objects.exists())

    def test_sleep_hours_range(self):
        self.client.post(reverse("checkin"), self.payload(sleep_hours=25))
        self.client.post(reverse("checkin"), self.payload(sleep_hours=-1))
        self.assertFalse(DailyCheckin.objects.exists())

    def test_future_date_rejected(self):
        self.client.post(reverse("checkin"), self.payload(date=(self.today + timedelta(days=1)).isoformat()))
        self.assertFalse(DailyCheckin.objects.exists())

    def test_activity_requires_minutes(self):
        self.client.post(reverse("checkin"), self.payload(activity_minutes=0))
        self.assertFalse(DailyCheckin.objects.exists())

    def test_second_checkin_same_day_is_rejected(self):
        self.client.post(reverse("checkin"), self.payload(mood=2))
        response = self.client.post(reverse("checkin"), self.payload(mood=5))
        self.assertEqual(DailyCheckin.objects.filter(user=self.user).count(), 1)
        self.assertRedirects(response, reverse("history"))
        self.assertEqual(DailyCheckin.objects.get(user=self.user).mood, 2)

    def test_past_date_checkin_is_rejected(self):
        response = self.client.post(
            reverse("checkin"),
            self.payload(date=(self.today - timedelta(days=1)).isoformat()),
        )
        self.assertRedirects(response, reverse("checkin"))
        self.assertFalse(DailyCheckin.objects.exists())

    def test_today_checkin_page_disables_repeat_submission(self):
        self.client.post(reverse("checkin"), self.payload())
        response = self.client.get(reverse("checkin"))
        self.assertContains(response, "Hôm nay bạn đã check-in")
        self.assertNotContains(response, 'name="mood"')

    def test_fourteen_days_of_sample_data_and_history(self):
        """Demo thầy yêu cầu: nhập 14 ngày dữ liệu mẫu và xem lại lịch sử."""
        seed_user_data(self.user, days=14)
        self.assertEqual(DailyCheckin.objects.filter(user=self.user).count(), 14)
        r = self.client.get(reverse("history"))
        self.assertEqual(r.status_code, 200)
        for offset in range(14):
            self.assertContains(r, (self.today - timedelta(days=offset)).strftime("%d/%m/%Y"))

    def test_seed_is_idempotent(self):
        seed_user_data(self.user, days=14)
        seed_user_data(self.user, days=14)
        self.assertEqual(DailyCheckin.objects.filter(user=self.user).count(), 14)
        self.assertEqual(self.user.habits.count(), 4)

    def test_api_checkin(self):
        h = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.user)}"}
        r = self.client.post("/api/checkins/", json.dumps(self.payload()), content_type="application/json", **h)
        self.assertEqual(r.status_code, 201)
        duplicate = self.client.post(
            "/api/checkins/",
            json.dumps(self.payload(mood=2)),
            content_type="application/json",
            **h,
        )
        self.assertEqual(duplicate.status_code, 409)
        past = self.client.post(
            "/api/checkins/",
            json.dumps(self.payload(date=(self.today - timedelta(days=1)).isoformat())),
            content_type="application/json",
            **h,
        )
        self.assertEqual(past.status_code, 400)
        bad = self.client.post("/api/checkins/", json.dumps(self.payload(mood=9, date="khong-phai-ngay")), content_type="application/json", **h)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(len(self.client.get("/api/checkins/", **h).json()["checkins"]), 1)


class JournalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a", password="Matkhau!2026x")
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})

    def test_create_read_edit_delete(self):
        r = self.client.post(reverse("journal_create"), {"title": "Hôm nay", "content": "Nội dung bí mật", "tags": "một, hai"})
        entry = JournalEntry.objects.get()
        self.assertRedirects(r, reverse("journal_detail", args=[entry.pk]))
        self.assertContains(self.client.get(reverse("journal_detail", args=[entry.pk])), "Nội dung bí mật")
        self.assertEqual(entry.tag_list, ["một", "hai"])
        self.client.post(reverse("journal_update", args=[entry.pk]), {"title": "Sửa", "content": "Mới", "tags": ""})
        entry.refresh_from_db()
        self.assertEqual((entry.title, entry.content), ("Sửa", "Mới"))
        self.client.post(reverse("journal_delete", args=[entry.pk]))
        self.assertFalse(JournalEntry.objects.exists())

    def test_search_decrypts_in_python(self):
        JournalEntry.objects.create(user=self.user, title="A", content="mùa thi căng thẳng")
        JournalEntry.objects.create(user=self.user, title="B", content="đi dạo")
        r = self.client.get(reverse("journal_list"), {"q": "căng thẳng"})
        self.assertContains(r, "mùa thi")
        self.assertNotContains(r, "đi dạo")
