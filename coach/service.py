"""Task 5 - AI coach nhẹ: gom số liệu tuần -> prompt -> (LLM hoặc bộ luật) -> lọc an toàn -> lưu."""
import logging
from datetime import timedelta

from django.utils import timezone

from habits.models import Notification
from habits.services import deliver_notification, get_habit_stats
from insights.services import period_stats

from . import llm, prompts, safety
from .models import CoachReport

logger = logging.getLogger(__name__)


class ConsentRequired(Exception):
    """Người dùng chưa đồng ý cho AI coach đọc số liệu."""


def build_week_data(user, today=None):
    """Số liệu tổng hợp 7 ngày (KHÔNG có nội dung journal, KHÔNG có tên/email)."""
    today = today or timezone.localdate()
    now = period_stats(user, "week", today)
    before = period_stats(user, "week", today - timedelta(days=7))
    habits = []
    for habit in user.habits.filter(is_active=True):
        stats = get_habit_stats(habit, today)
        habits.append({
            "done_last_7_days": habit.logs.filter(date__gte=today - timedelta(days=6), date__lte=today).count(),
            "current_streak": stats["current_streak"],
            "done_today": stats["done_today"],
        })
    summary = now["summary"]
    return {
        "period": {"start": summary["start"], "end": summary["end"]},
        "checkin_days": summary["checkin_days"],
        "avg_mood_1_to_5": summary["avg_mood"],
        "avg_sleep_hours": summary["avg_sleep_hours"],
        "activity_minutes": summary["total_activity_minutes"],
        "habit_completion_percent": summary["completion_percent"],
        "previous_week_avg_mood": before["summary"]["avg_mood"],
        "previous_week_avg_sleep": before["summary"]["avg_sleep_hours"],
        "habits": habits,
        "daily": [
            {"date": r["date"], "mood": r["mood"], "sleep_hours": r["sleep_hours"],
             "activity_minutes": r["activity_minutes"], "habits_done": r["habits_done"]}
            for r in now["daily"]
        ],
    }


def rule_based_report(data):
    """Bộ luật dự phòng (chạy khi không có API key hoặc LLM lỗi). Không bao giờ chẩn đoán."""
    patterns, goals, actions = [], [], []
    mood, sleep = data["avg_mood_1_to_5"], data["avg_sleep_hours"]
    completion = data["habit_completion_percent"]
    prev_mood = data["previous_week_avg_mood"]

    if data["checkin_days"] == 0:
        return {
            "summary": "Tuần này Mầm chưa có check-in nào của bạn nên chưa thể nhận xét. Chỉ cần 1 phút mỗi ngày là đủ để bắt đầu.",
            "patterns": [],
            "goals": ["Check-in tâm trạng và giấc ngủ vào cùng một giờ mỗi ngày trong 3 ngày tới."],
            "actions": ["Đặt nhắc nhở check-in ngay sau bữa tối."],
        }
    if sleep is not None and sleep < 6.5:
        patterns.append(f"Giấc ngủ trung bình {sleep} giờ/đêm, khá ngắn so với mức 7 giờ trở lên mà nhiều người cần.")
        goals.append("Đi ngủ sớm hơn 15 phút trong 3 đêm tới.")
        actions.append("Tắt màn hình 20 phút trước khi ngủ.")
    if mood is not None and prev_mood is not None and mood <= prev_mood - 0.5:
        patterns.append(f"Tâm trạng trung bình giảm từ {prev_mood} xuống {mood} so với tuần trước.")
        actions.append("Dành 10 phút làm điều bạn thích và nói chuyện với một người bạn tin tưởng.")
    if mood is not None and mood <= 2.5:
        patterns.append("Tâm trạng tự đánh giá của bạn thấp trong cả tuần.")
        actions.append("Ưu tiên nghỉ ngơi, giảm bớt một việc không gấp và chia sẻ với người thân.")
    if completion is not None and completion < 50:
        weakest = min(data["habits"], key=lambda h: h["done_last_7_days"], default=None)
        patterns.append(f"Bạn hoàn thành khoảng {completion}% lượt thói quen đã đặt trong tuần.")
        goals.append(
            "Chọn một thói quen đang khó giữ, giảm xuống mức 2 phút mỗi ngày trong 3 ngày tới."
            if weakest else "Chọn 1 thói quen nhỏ và làm trong 2 phút mỗi ngày."
        )
    at_risk = [h for h in data["habits"] if h["current_streak"] > 0 and not h["done_today"]]
    if at_risk:
        top = max(at_risk, key=lambda h: h["current_streak"])
        patterns.append(f"Một thói quen đang có chuỗi {top['current_streak']} ngày nhưng hôm nay chưa được đánh dấu.")
        actions.append("Hoàn thành thói quen đó hôm nay nếu bạn vẫn muốn tiếp tục chuỗi.")
    if data["activity_minutes"] < 60:
        goals.append("Đi bộ 10 phút mỗi ngày, có thể vừa đi vừa nghe nhạc.")

    if not patterns:
        summary = (
            f"Tuần này bạn check-in {data['checkin_days']}/7 ngày, ngủ trung bình {sleep} giờ và "
            f"hoàn thành {completion if completion is not None else 0}% thói quen. Nhịp độ khá ổn, hãy giữ nhé!"
        )
        goals = goals or ["Giữ nhịp thói quen hiện tại và thử tăng nhẹ một mục tiêu nhỏ."]
        actions = actions or ["Ghi lại điều bạn thấy biết ơn hôm nay."]
    else:
        summary = (
            f"Tuần này bạn check-in {data['checkin_days']}/7 ngày. Mầm thấy có {len(patterns)} điều có thể "
            "điều chỉnh nhẹ nhàng, không cần hoàn hảo, chỉ cần một bước nhỏ."
        )
    return {"summary": summary, "patterns": patterns, "goals": goals, "actions": actions}


def generate_report(user, today=None):
    if not user.consent_ai:
        raise ConsentRequired
    today = today or timezone.localdate()
    data = build_week_data(user, today)

    raw, source = llm.call_llm_json(prompts.build_weekly_prompt(data)), CoachReport.SOURCE_LLM
    if not raw or not raw.get("summary"):
        raw, source = rule_based_report(data), CoachReport.SOURCE_RULES
    clean = safety.sanitize_report(raw)

    report, _ = CoachReport.objects.update_or_create(
        user=user, week_end=today,
        defaults={
            "week_start": today - timedelta(days=6), "summary": clean["summary"],
            "patterns": clean["patterns"], "goals": clean["goals"], "actions": clean["actions"],
            "source": source,
        },
    )
    notification, created = Notification.objects.get_or_create(
        user=user, kind=Notification.KIND_COACH, habit=None, day=today,
        defaults={"title": "Có bản tóm tắt tuần mới", "body": "AI coach vừa tóm tắt tuần của bạn."},
    )
    if created:
        deliver_notification(notification)
    return report


def answer_question(user, question, conversation=None):
    """Trả lời một câu hỏi ngắn. Câu nhạy cảm bị chặn TRƯỚC khi tới AI."""
    screened = safety.screen_text(question)
    if screened["level"] != "ok":
        return {
            "level": screened["level"],
            "summary": screened["reply"],
            "actions": [],
            "source": "safety",
        }
    if not user.consent_ai:
        raise ConsentRequired

    data = build_week_data(user)
    raw = llm.call_llm_json(prompts.build_question_prompt(question, data, conversation))
    source = CoachReport.SOURCE_LLM
    if not raw or not raw.get("summary"):
        logger.warning("AI coach returned no summary; using the rule-based answer.")
        raw = _rule_based_answer(question)
        source = CoachReport.SOURCE_RULES
    clean = safety.sanitize_report(raw)
    return {
        "level": "ok",
        "summary": clean["summary"],
        "actions": clean["actions"] + clean["goals"][:1],
        "source": source,
    }


def _rule_based_answer(question):
    text = safety.normalize(question)
    if any(w in text for w in ("ngu", "mat ngu", "thuc khuya")):
        return {"summary": "Giờ giấc đều đặn thường quan trọng hơn ngủ thật nhiều một đêm.",
                "actions": ["Chọn một giờ đi ngủ cố định và lùi sớm dần 15 phút."], "goals": []}
    if any(w in text for w in ("cang thang", "ap luc", "stress", "met")):
        return {"summary": "Cảm giác quá tải là chuyện thường gặp. Chia việc thành bước nhỏ sẽ nhẹ hơn.",
                "actions": ["Hít thở chậm 1 phút rồi chọn một việc nhỏ nhất để bắt đầu."], "goals": []}
    if any(w in text for w in ("luoi", "tri hoan", "dong luc", "thoi quen", "ky luat")):
        return {"summary": "Bắt đầu nhỏ giúp bạn dễ giữ thói quen hơn là đặt mục tiêu lớn.",
                "actions": ["Giảm thói quen xuống còn 2 phút và gắn nó với một việc bạn đã làm mỗi ngày."], "goals": []}
    return {"summary": "Cảm ơn bạn đã chia sẻ. Hãy chọn một điều nhỏ có thể làm hôm nay.",
            "actions": ["Viết ra một việc 5 phút bạn có thể làm ngay."], "goals": []}
