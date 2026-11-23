"""Task 1 - kiểm thử: JWT, mật khẩu băm, phân quyền, mã hóa journal, API xóa/xuất, thống kê ẩn danh."""
import json
import os
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_access_token, create_refresh_token
from habits.models import BrowserPushSubscription, Habit
from insights.models import DailyWellbeingIndex
from tracking.models import JournalEntry


class ResetAccountsCommandTests(TestCase):
    def test_requires_confirmation_before_deleting_users(self):
        existing = User.objects.create_user("existing", password="old-password-123")
        with patch.dict(os.environ, {
            "ACCOUNT_USER_PASSWORD": "user-password-123",
            "ACCOUNT_ADMIN_PASSWORD": "admin-password-123",
        }):
            with self.assertRaises(CommandError):
                call_command("reset_accounts")
        self.assertTrue(User.objects.filter(pk=existing.pk).exists())

    def test_requires_passwords_before_deleting_users(self):
        existing = User.objects.create_user("existing", password="old-password-123")
        with patch.dict(os.environ, {"ACCOUNT_USER_PASSWORD": "", "ACCOUNT_ADMIN_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("reset_accounts", confirm=True)
        self.assertTrue(User.objects.filter(pk=existing.pk).exists())

    def test_recreates_only_user_and_admin_and_clears_user_data(self):
        user_password = "test-user-password-123"
        admin_password = "test-admin-password-123"
        previous_user = User.objects.create_user("previous", password="old-password-123")
        Habit.objects.create(user=previous_user, name="Old habit")
        JournalEntry.objects.create(user=previous_user, title="Old journal", content="Private")
        output = StringIO()
        with patch.dict(os.environ, {
            "ACCOUNT_USER_PASSWORD": user_password,
            "ACCOUNT_ADMIN_PASSWORD": admin_password,
        }):
            call_command("reset_accounts", confirm=True, stdout=output)

        users = {user.username: user for user in User.objects.all()}
        self.assertEqual(set(users), {"nguyenvana", "thaoquyen"})
        self.assertEqual(users["nguyenvana"].role, User.ROLE_USER)
        self.assertTrue(users["nguyenvana"].check_password(user_password))
        self.assertEqual(users["thaoquyen"].role, User.ROLE_ADMIN)
        self.assertTrue(users["thaoquyen"].is_superuser)
        self.assertTrue(users["thaoquyen"].check_password(admin_password))
        self.assertFalse(Habit.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())
        self.assertNotIn(user_password, output.getvalue())
        self.assertNotIn(admin_password, output.getvalue())


def bearer(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


class AuthApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, url, data, **extra):
        return self.client.post(url, json.dumps(data), content_type="application/json", **extra)

    def test_register_login_and_me(self):
        r = self.post("/api/auth/register/", {"username": "linh", "password": "Matkhau!2026x"})
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        r = self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {body['access']}")
        self.assertEqual(r.json()["username"], "linh")
        self.assertEqual(r.json()["role"], "user")
        r = self.post("/api/auth/login/", {"username": "linh", "password": "Matkhau!2026x"})
        self.assertEqual(r.status_code, 200)

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"])
    def test_password_is_hashed(self):
        self.post("/api/auth/register/", {"username": "linh", "password": "Matkhau!2026x"})
        self.assertTrue(User.objects.get(username="linh").password.startswith("pbkdf2_"))

    def test_weak_password_rejected(self):
        r = self.post("/api/auth/register/", {"username": "linh", "password": "12345678"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_tampered_expired_tokens(self):
        user = User.objects.create_user("a", password="Matkhau!2026x")
        self.assertEqual(self.client.get("/api/me/").status_code, 401)
        self.assertEqual(self.client.get("/api/me/", HTTP_AUTHORIZATION="Bearer abc.def.ghi").status_code, 401)
        good = create_access_token(user)
        self.assertEqual(self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {good}x").status_code, 401)
        expired = create_access_token(user, lifetime=timedelta(seconds=-10))
        self.assertEqual(self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {expired}").status_code, 401)

    def test_refresh_token_cannot_be_used_as_access(self):
        user = User.objects.create_user("a", password="Matkhau!2026x")
        refresh = create_refresh_token(user)
        self.assertEqual(self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {refresh}").status_code, 401)
        r = self.post("/api/auth/refresh/", {"refresh": refresh})
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json())

    def test_changing_password_invalidates_old_tokens(self):
        user = User.objects.create_user("a", password="Matkhau!2026x")
        token = create_access_token(user)
        user.set_password("MatkhauMoi!2026")
        user.save()
        self.assertEqual(self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {token}").status_code, 401)

    def test_lockout_after_repeated_failures(self):
        User.objects.create_user("a", password="Matkhau!2026x")
        for _ in range(5):
            self.assertEqual(self.post("/api/auth/login/", {"username": "a", "password": "sai"}).status_code, 401)
        self.assertEqual(self.post("/api/auth/login/", {"username": "a", "password": "Matkhau!2026x"}).status_code, 429)


class WebAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("a", password="Matkhau!2026x")

    def test_login_sets_httponly_jwt_cookie(self):
        r = self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        cookie = r.cookies["mam_access"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_pages_require_login(self):
        for name in ("dashboard", "habit_list", "checkin", "journal_list", "coach", "privacy", "notifications"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/accounts/login/", r["Location"])

    def test_cookie_cannot_write_through_api(self):
        """Cookie chỉ đọc được API bằng GET; ghi dữ liệu qua API bắt buộc Bearer (chống CSRF)."""
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})
        self.assertEqual(self.client.get("/api/habits/").status_code, 200)
        r = self.client.post("/api/habits/", json.dumps({"name": "x"}), content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_logout_clears_cookie(self):
        self.client.post(reverse("login"), {"username": "a", "password": "Matkhau!2026x"})
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)


class PrivacyIsolationTests(TestCase):
    """Demo: user A không đọc được dữ liệu user B; admin chỉ xem thống kê ẩn danh."""

    def setUp(self):
        cache.clear()
        self.a = User.objects.create_user("usera", password="Matkhau!2026x")
        self.b = User.objects.create_user("userb", password="Matkhau!2026x")
        self.admin = User.objects.create_user("boss", password="Matkhau!2026x", role=User.ROLE_ADMIN)
        self.secret = JournalEntry.objects.create(user=self.b, title="Của B", content="Bí mật rất riêng của B")
        self.habit_b = Habit.objects.create(user=self.b, name="Habit của B")

    def test_api_user_a_cannot_touch_b(self):
        h = bearer(self.a)
        url = f"/api/journals/{self.secret.pk}/"
        self.assertEqual(self.client.get(url, **h).status_code, 404)
        self.assertEqual(self.client.delete(url, **h).status_code, 404)
        self.assertEqual(self.client.put(url, json.dumps({"title": "x"}), content_type="application/json", **h).status_code, 404)
        self.assertEqual(self.client.get(f"/api/habits/{self.habit_b.pk}/", **h).status_code, 404)
        self.assertEqual(self.client.post(f"/api/habits/{self.habit_b.pk}/check/", **h).status_code, 404)
        self.assertEqual(self.client.get("/api/journals/", **h).json()["journals"], [])
        self.assertEqual(self.client.get("/api/habits/", **h).json()["habits"], [])
        self.assertTrue(JournalEntry.objects.filter(pk=self.secret.pk).exists())

    def test_owner_can_read(self):
        r = self.client.get(f"/api/journals/{self.secret.pk}/", **bearer(self.b))
        self.assertEqual(r.json()["content"], "Bí mật rất riêng của B")

    def test_web_user_a_cannot_open_b_pages(self):
        self.client.post(reverse("login"), {"username": "usera", "password": "Matkhau!2026x"})
        self.assertEqual(self.client.get(reverse("journal_detail", args=[self.secret.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("journal_update", args=[self.secret.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("habit_detail", args=[self.habit_b.pk])).status_code, 404)

    def test_admin_role_cannot_read_user_journal(self):
        self.assertEqual(self.client.get(f"/api/journals/{self.secret.pk}/", **bearer(self.admin)).status_code, 404)

    def test_journal_content_is_encrypted_in_database(self):
        with connection.cursor() as cur:
            cur.execute("SELECT content FROM tracking_journalentry WHERE id = %s", [self.secret.pk])
            raw = cur.fetchone()[0]
        self.assertNotIn("Bí mật", raw)
        self.assertTrue(raw.startswith("gAAAA"))
        self.assertEqual(JournalEntry.objects.get(pk=self.secret.pk).content, "Bí mật rất riêng của B")

    def test_admin_stats_requires_admin_role(self):
        self.assertEqual(self.client.get("/api/admin/stats/", **bearer(self.a)).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/stats/").status_code, 401)

    def test_admin_stats_are_anonymous(self):
        r = self.client.get("/api/admin/stats/", **bearer(self.admin))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["available"])
        text = json.dumps(data, ensure_ascii=False)
        for forbidden in ("usera", "userb", "Bí mật", "Của B", "example.com"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(data["journals"]["total_entries"], 1)

    def test_admin_stats_hidden_when_too_few_users(self):
        self.a.delete()
        self.b.delete()
        data = self.client.get("/api/admin/stats/", **bearer(self.admin)).json()
        self.assertFalse(data["available"])

    def test_admin_web_page_role_check(self):
        self.client.post(reverse("login"), {"username": "usera", "password": "Matkhau!2026x"})
        self.assertEqual(self.client.get(reverse("admin_stats")).status_code, 403)
        self.client.post(reverse("logout"))
        self.client.post(reverse("login"), {"username": "boss", "password": "Matkhau!2026x"})
        r = self.client.get(reverse("admin_stats"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "userb")

    def test_export_my_data(self):
        DailyWellbeingIndex.objects.create(user=self.b, score=75, mood_score=80)
        BrowserPushSubscription.objects.create(
            user=self.b, endpoint="https://fcm.googleapis.com/fcm/send/export",
            p256dh="public-key", auth="auth-secret",
        )
        r = self.client.get("/api/me/export/", **bearer(self.b))
        data = json.loads(r.content)
        self.assertEqual(data["journals"][0]["content"], "Bí mật rất riêng của B")
        self.assertEqual(data["habits"][0]["name"], "Habit của B")
        self.assertEqual(data["wellbeing_indices"][0]["score"], 75)
        self.assertIn("fcm.googleapis.com", data["push_subscriptions"][0]["endpoint"])
        self.assertIn("attachment", r["Content-Disposition"])

    def test_delete_my_data_keeps_account(self):
        DailyWellbeingIndex.objects.create(user=self.b, score=75)
        BrowserPushSubscription.objects.create(
            user=self.b, endpoint="https://fcm.googleapis.com/fcm/send/delete",
            p256dh="public-key", auth="auth-secret",
        )
        r = self.client.delete("/api/me/data/", **bearer(self.b))
        self.assertEqual(r.json()["deleted"]["journals"], 1)
        self.assertFalse(JournalEntry.objects.filter(user=self.b).exists())
        self.assertFalse(DailyWellbeingIndex.objects.filter(user=self.b).exists())
        self.assertFalse(BrowserPushSubscription.objects.filter(user=self.b).exists())
        self.assertTrue(User.objects.filter(pk=self.b.pk).exists())

    def test_delete_account_needs_password(self):
        h = bearer(self.b)
        r = self.client.delete("/api/me/", json.dumps({"password": "sai"}), content_type="application/json", **h)
        self.assertEqual(r.status_code, 403)
        r = self.client.delete("/api/me/", json.dumps({"password": "Matkhau!2026x"}), content_type="application/json", **h)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.b.pk).exists())
        self.assertFalse(JournalEntry.objects.exists())


class SmokeTests(TestCase):
    """Mọi trang chính phải hiển thị được (không lỗi template) cho người đã đăng nhập."""

    def test_all_pages_render(self):
        from accounts.sample_data import seed_user_data

        user = User.objects.create_user("smoke", password="Matkhau!2026x", consent_ai=True)
        seed_user_data(user, 30)
        entry = JournalEntry.objects.filter(user=user).first()
        habit = user.habits.first()
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("register")).status_code, 200)
        self.client.post(reverse("login"), {"username": "smoke", "password": "Matkhau!2026x"})
        pages = [
            reverse("dashboard"), reverse("habit_list"), reverse("habit_create"),
            reverse("habit_detail", args=[habit.pk]), reverse("habit_update", args=[habit.pk]),
            reverse("habit_delete", args=[habit.pk]), reverse("checkin"), reverse("history"),
            reverse("journal_list"), reverse("journal_create"), reverse("journal_detail", args=[entry.pk]),
            reverse("journal_update", args=[entry.pk]), reverse("journal_delete", args=[entry.pk]),
            reverse("notifications"), reverse("coach"), reverse("privacy"), reverse("export_data"),
        ]
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/khong-ton-tai/").status_code, 404)

    def test_sample_data_button_and_delete_flow(self):
        user = User.objects.create_user("smoke2", password="Matkhau!2026x")
        self.client.post(reverse("login"), {"username": "smoke2", "password": "Matkhau!2026x"})
        self.client.post(reverse("sample_data"))
        self.assertEqual(user.checkins.count(), 30)
        self.client.post(reverse("delete_data"))                       # chưa tick xác nhận -> không xóa
        self.assertEqual(user.checkins.count(), 30)
        self.client.post(reverse("delete_data"), {"confirm": "yes"})
        self.assertEqual(user.checkins.count(), 0)
        self.client.post(reverse("delete_account"), {"password": "sai"})
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.client.post(reverse("delete_account"), {"password": "Matkhau!2026x"})
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
