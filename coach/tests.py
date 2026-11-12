"""Task 5 - kiểm thử AI coach: đồng ý của người dùng, bộ lọc nhạy cảm, disclaimer, không lộ journal."""
import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.demo import seed_user_data
from accounts.models import User
from accounts.tokens import create_access_token
from coach import safety
from coach.service import ConsentRequired, build_week_data, generate_report
from tracking.models import JournalEntry


def bearer(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


class SafetyFilterTests(TestCase):
    def test_medical_questions_refused(self):
        for text in ("Mình có bị trầm cảm không?", "bác sĩ chẩn đoán giúp mình", "nên uống thuốc ngủ nào",
                     "toi co bi tram cam khong", "Rối loạn lo âu là gì"):
            self.assertEqual(safety.screen_text(text)["level"], "medical", text)
        self.assertIn("không thể chẩn đoán", safety.screen_text("chẩn đoán giúp mình")["reply"])

    def test_crisis_text_gets_support_message(self):
        res = safety.screen_text("Mình muốn chết quá")
        self.assertEqual(res["level"], "crisis")
        self.assertIn("115", res["reply"])

    def test_normal_text_passes(self):
        for text in ("Mình hay trì hoãn thói quen buổi tối", "Hôm nay mình mệt", "Bài tập này thuộc về nhóm mình"):
            self.assertEqual(safety.screen_text(text)["level"], "ok", text)

    def test_sanitize_removes_diagnosis_from_ai_output(self):
        raw = {"summary": "Bạn có dấu hiệu của trầm cảm.", "patterns": ["Ngủ ít", "Nên uống thuốc ngủ"],
               "goals": ["Đi bộ 10 phút"], "actions": ["Được chẩn đoán rối loạn lo âu"]}
        clean = safety.sanitize_report(raw)
        text = json.dumps(clean, ensure_ascii=False)
        self.assertNotIn("trầm cảm", text)
        self.assertNotIn("thuốc", text)
        self.assertNotIn("chẩn đoán", text)
        self.assertEqual(clean["patterns"], ["Ngủ ít"])
        self.assertEqual(clean["goals"], ["Đi bộ 10 phút"])
        self.assertTrue(clean["flagged"])


class CoachReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("coachuser", password="Matkhau!2026x", consent_ai=True)
        seed_user_data(self.user, 14)

    def test_requires_consent(self):
        self.user.consent_ai = False
        self.user.save()
        with self.assertRaises(ConsentRequired):
            generate_report(self.user)
        r = self.client.post("/api/coach/weekly/", **bearer(self.user))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"], "consent_required")

    def test_weekly_summary_has_disclaimer(self):
        """Demo thầy yêu cầu: AI trả bản tóm tắt tuần có disclaimer."""
        r = self.client.post("/api/coach/weekly/", **bearer(self.user))
        self.assertEqual(r.status_code, 201)
        data = r.json()
        self.assertTrue(data["summary"])
        self.assertTrue(data["goals"])
        self.assertIn("không phải chẩn đoán", data["disclaimer"])
        self.assertEqual(data["source"], "rules")        # không có API key -> bộ luật dự phòng
        self.assertEqual(self.client.get("/api/coach/weekly/", **bearer(self.user)).status_code, 200)

    def test_prompt_data_never_contains_journal_or_identity(self):
        JournalEntry.objects.create(user=self.user, title="Tiêu đề riêng", content="Nội dung rất riêng tư")
        blob = json.dumps(build_week_data(self.user), ensure_ascii=False)
        self.assertNotIn("Nội dung rất riêng tư", blob)
        self.assertNotIn("Tiêu đề riêng", blob)
        self.assertNotIn(self.user.username, blob)
        self.assertNotIn("example.com", blob)

    def test_llm_output_is_sanitized(self):
        fake = {"summary": "Bạn bị trầm cảm.", "patterns": [], "goals": ["Ngủ sớm 15 phút"], "actions": ["Uống thuốc an thần"]}
        with mock.patch("coach.service.llm.call_llm_json", return_value=fake):
            report = generate_report(self.user)
        self.assertEqual(report.source, "llm")
        blob = json.dumps([report.summary, report.patterns, report.goals, report.actions], ensure_ascii=False)
        self.assertNotIn("trầm cảm", blob)
        self.assertNotIn("thuốc", blob)
        self.assertIn("Ngủ sớm 15 phút", blob)

    def test_llm_failure_falls_back_to_rules(self):
        with mock.patch("coach.service.llm.call_llm_json", return_value=None):
            self.assertEqual(generate_report(self.user).source, "rules")

    def test_sensitive_question_never_reaches_llm(self):
        self.client.post(reverse("login"), {"username": "coachuser", "password": "Matkhau!2026x"})
        with mock.patch("coach.service.llm.call_llm_json") as llm:
            self.client.post(reverse("coach_ask"), {"question": "Mình có bị trầm cảm không?"})
            r = self.client.get(reverse("coach"))
            llm.assert_not_called()
        self.assertContains(r, "không thể chẩn đoán")

    def test_no_data_week_gives_gentle_message(self):
        newbie = User.objects.create_user("newbie", password="Matkhau!2026x", consent_ai=True)
        report = generate_report(newbie)
        self.assertIn("chưa có check-in", report.summary)

    def test_coach_page(self):
        self.client.post(reverse("login"), {"username": "coachuser", "password": "Matkhau!2026x"})
        self.client.post(reverse("coach_generate"))
        r = self.client.get(reverse("coach"))
        self.assertContains(r, "không phải chẩn đoán")
