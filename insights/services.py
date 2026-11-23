"""
Task 4 - tổng hợp số liệu theo tuần/tháng cho dashboard và tạo thông báo "sắp mất streak".
"""
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from habits.models import Habit, HabitLog, Notification
from habits.services import calculate_streaks, deliver_notification, get_done_dates
from tracking.models import DailyCheckin

from .models import DailyWellbeingIndex

PERIODS = {"week": 7, "month": 30}
WELLBEING_INDEX_VERSION = 2


def _avg(values, digits=1):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), digits) if values else None


def update_daily_wellbeing_indices(user, start, end):
    """Lưu index 0-100 theo ngày, chỉ cập nhật khi dữ liệu nguồn của ngày đó thay đổi."""
    habits = list(Habit.objects.filter(user=user, is_active=True))
    habit_ids = sorted(habit.pk for habit in habits)
    checkins = {
        c.date: c
        for c in DailyCheckin.objects.filter(user=user, date__range=(start, end))
    }
    logs = HabitLog.objects.filter(habit__in=habits, date__range=(start, end))
    done_by_day = {}
    for day in logs.values_list("date", flat=True):
        done_by_day[day] = done_by_day.get(day, 0) + 1

    existing = {
        index.date: index
        for index in DailyWellbeingIndex.objects.filter(user=user, date__range=(start, end))
    }
    weights = {"mood": 35, "sleep": 25, "activity": 10, "habit": 30}
    day = start
    while day <= end:
        c = checkins.get(day)
        parts = {}
        if c:
            parts["mood"] = round((c.mood - 1) * 25, 1)
            parts["sleep"] = round(min(100, c.sleep_hours / 8 * 100), 1)
            parts["activity"] = round(min(100, c.activity_minutes / 30 * 100), 1)
        if habits:
            parts["habit"] = round(done_by_day.get(day, 0) * 100 / len(habits), 1)

        coverage = sum(weights[name] for name in parts)
        score = (
            round(sum(parts[name] * weights[name] for name in parts) / coverage, 1)
            if c and coverage else None
        )
        source = {
            "version": WELLBEING_INDEX_VERSION,
            "habits": habit_ids,
            "done": done_by_day.get(day, 0),
            "checkin": (
                [c.mood, c.sleep_hours, c.activity_minutes] if c else None
            ),
        }
        fingerprint = hashlib.sha256(
            json.dumps(source, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()
        index = existing.get(day)
        if index and index.source_fingerprint == fingerprint:
            day += timedelta(days=1)
            continue

        values = {
            "score": score,
            "mood_score": parts.get("mood"),
            "sleep_score": parts.get("sleep"),
            "activity_score": parts.get("activity"),
            "habit_score": parts.get("habit"),
            "coverage_percent": coverage,
            "source_fingerprint": fingerprint,
        }
        if index:
            for name, value in values.items():
                setattr(index, name, value)
            index.save(update_fields=[*values, "updated_at"])
        else:
            DailyWellbeingIndex.objects.create(user=user, date=day, **values)
        day += timedelta(days=1)


def period_stats(user, period="week", today=None):
    """
    Số liệu của chính `user` trong 7 ngày (week) hoặc 30 ngày (month) gần nhất.

    Trả về dict JSON-an-toàn: `daily` (mỗi ngày), `weekly` (gom theo khối 7 ngày) và `summary`.
    """
    days = PERIODS.get(period, 7)
    today = today or timezone.localdate()
    start = today - timedelta(days=days - 1)

    update_daily_wellbeing_indices(user, start, today)

    habits = list(Habit.objects.filter(user=user, is_active=True))
    planned = len(habits)
    logs = HabitLog.objects.filter(habit__in=habits, date__range=(start, today))
    done_by_day = {}
    for day in logs.values_list("date", flat=True):
        done_by_day[day] = done_by_day.get(day, 0) + 1
    checkins = {c.date: c for c in DailyCheckin.objects.filter(user=user, date__range=(start, today))}
    indices = {
        i.date: i
        for i in DailyWellbeingIndex.objects.filter(user=user, date__range=(start, today))
    }

    daily = []
    for i in range(days):
        day = start + timedelta(days=i)
        c = checkins.get(day)
        done = done_by_day.get(day, 0)
        index = indices.get(day)
        daily.append({
            "date": day.isoformat(),
            "label": day.strftime("%d/%m"),
            "mood": c.mood if c else None,
            "sleep_hours": c.sleep_hours if c else None,
            "activity_minutes": c.activity_minutes if c else None,
            "habits_done": done,
            "habits_planned": planned,
            "completion_percent": round(done * 100 / planned) if planned else None,
            "wellbeing_index": index.score if index else None,
            "wellbeing_index_coverage": index.coverage_percent if index else 0,
            "index_mood": index.mood_score if index else None,
            "index_sleep": index.sleep_score if index else None,
            "index_activity": index.activity_score if index else None,
            "index_habit": index.habit_score if index else None,
        })

    def bucket(rows):
        done = sum(r["habits_done"] for r in rows)
        total = sum(r["habits_planned"] for r in rows)
        return {
            "label": f'{rows[0]["label"]}–{rows[-1]["label"]}',
            "avg_mood": _avg(r["mood"] for r in rows),
            "avg_sleep_hours": _avg(r["sleep_hours"] for r in rows),
            "activity_minutes": sum(r["activity_minutes"] or 0 for r in rows),
            "habits_done": done,
            "completion_percent": round(done * 100 / total) if total else None,
            "avg_wellbeing_index": _avg(r["wellbeing_index"] for r in rows),
            "avg_wellbeing_index_coverage": _avg(
                r["wellbeing_index_coverage"] for r in rows if r["wellbeing_index"] is not None
            ),
        }

    weekly = [bucket(daily[i:i + 7]) for i in range(0, days, 7)]
    total_done = sum(r["habits_done"] for r in daily)
    streaks = [calculate_streaks(get_done_dates(h), today)[0] for h in habits]
    summary = {
        "period": period if period in PERIODS else "week",
        "days": days,
        "start": start.isoformat(),
        "end": today.isoformat(),
        "avg_mood": _avg(r["mood"] for r in daily),
        "avg_sleep_hours": _avg(r["sleep_hours"] for r in daily),
        "total_activity_minutes": sum(r["activity_minutes"] or 0 for r in daily),
        "checkin_days": sum(1 for r in daily if r["mood"] is not None),
        "habits_done": total_done,
        "completion_percent": round(total_done * 100 / (planned * days)) if planned else None,
        "avg_wellbeing_index": _avg(r["wellbeing_index"] for r in daily),
        "avg_wellbeing_index_coverage": _avg(
            r["wellbeing_index_coverage"] for r in daily if r["wellbeing_index"] is not None
        ),
        "best_current_streak": max(streaks, default=0),
        "active_habits": planned,
    }
    return {"summary": summary, "daily": daily, "weekly": weekly}


def streak_risks(user, today=None):
    """Các thói quen có chuỗi đang chạy nhưng hôm nay chưa làm (sẽ mất chuỗi nếu hết ngày)."""
    today = today or timezone.localdate()
    risks = []
    for habit in Habit.objects.filter(user=user, is_active=True):
        done = get_done_dates(habit)
        if today in done:
            continue
        current, _ = calculate_streaks(done, today)
        if current > 0:
            risks.append({"habit": habit, "streak": current})
    return risks


def create_streak_risk_notifications(now=None, user=None):
    """
    Tạo thông báo "sắp mất chuỗi" cho thói quen có streak > 0 mà hôm nay chưa làm,
    từ STREAK_RISK_FROM_HOUR (mặc định 18h). Mỗi thói quen chỉ báo 1 lần/ngày.
    Trả về số thông báo mới.
    """
    now = now or timezone.localtime()
    if now.hour < settings.STREAK_RISK_FROM_HOUR:
        return 0
    today = now.date()
    habits = Habit.objects.filter(is_active=True).select_related("user")
    if user is not None:
        habits = habits.filter(user=user)
    created_count = 0
    for habit in habits:
        done = get_done_dates(habit)
        if today in done:
            continue
        current, _ = calculate_streaks(done, today)
        if current <= 0:
            continue
        notification, created = Notification.objects.get_or_create(
            user=habit.user, kind=Notification.KIND_STREAK_RISK, habit=habit, day=today,
            defaults={
                "title": f"Sắp mất chuỗi {current} ngày",
                "body": f"“{habit.name}” chưa được đánh dấu hôm nay. Làm ngay để giữ chuỗi {current} ngày nhé!",
            },
        )
        if created:
            deliver_notification(notification)
        created_count += int(created)
    return created_count


def create_wellbeing_trend_notifications(now=None, user=None):
    """Gửi một lời nhắc hỗ trợ/tuần khi index giảm rõ rệt và có đủ check-in để so sánh."""
    now = now or timezone.localtime()
    if now.hour < settings.WELLBEING_NUDGE_FROM_HOUR:
        return 0

    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    previous_week_start = week_start - timedelta(days=7)
    user_ids = DailyCheckin.objects.filter(
        date__range=(previous_week_start, today)
    ).values_list("user_id", flat=True).distinct()
    if user is not None:
        user_ids = user_ids.filter(user_id=user.pk)

    created_count = 0
    for candidate in get_user_model().objects.filter(pk__in=user_ids):
        if Notification.objects.filter(
            user=candidate, kind=Notification.KIND_WELLBEING, day=week_start
        ).exists():
            continue

        current = period_stats(candidate, "week", today)
        previous = period_stats(candidate, "week", today - timedelta(days=7))
        current_scores = [
            row["wellbeing_index"] for row in current["daily"]
            if row["mood"] is not None and row["wellbeing_index"] is not None
        ]
        previous_scores = [
            row["wellbeing_index"] for row in previous["daily"]
            if row["mood"] is not None and row["wellbeing_index"] is not None
        ]
        if len(current_scores) < 3 or len(previous_scores) < 3:
            continue
        current_average = _avg(current_scores)
        previous_average = _avg(previous_scores)
        if previous_average - current_average < settings.WELLBEING_NUDGE_DROP_POINTS:
            continue

        notification, created = Notification.objects.get_or_create(
            user=candidate,
            kind=Notification.KIND_WELLBEING,
            habit=None,
            day=week_start,
            defaults={
                "title": "Dành một chút thời gian cho bản thân",
                "body": (
                    "Chỉ số wellbeing tham khảo của bạn thấp hơn tuần trước. "
                    "Đây không phải đánh giá y tế; nếu hữu ích, hãy check-in và chọn một việc nhỏ để chăm sóc bản thân."
                ),
            },
        )
        if created:
            deliver_notification(notification)
        created_count += int(created)
    return created_count


def unread_count(user):
    return Notification.objects.filter(user=user, is_read=False).count()
