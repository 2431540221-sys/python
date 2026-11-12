"""
Task 4 - tổng hợp số liệu theo tuần/tháng cho dashboard và tạo thông báo "sắp mất streak".
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from habits.models import Habit, HabitLog, Notification
from habits.services import calculate_streaks, get_done_dates
from tracking.models import DailyCheckin

PERIODS = {"week": 7, "month": 30}


def _avg(values, digits=1):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), digits) if values else None


def period_stats(user, period="week", today=None):
    """
    Số liệu của chính `user` trong 7 ngày (week) hoặc 30 ngày (month) gần nhất.

    Trả về dict JSON-an-toàn: `daily` (mỗi ngày), `weekly` (gom theo khối 7 ngày) và `summary`.
    """
    days = PERIODS.get(period, 7)
    today = today or timezone.localdate()
    start = today - timedelta(days=days - 1)

    habits = list(Habit.objects.filter(user=user, is_active=True))
    planned = len(habits)
    logs = HabitLog.objects.filter(habit__in=habits, date__range=(start, today))
    done_by_day = {}
    for day in logs.values_list("date", flat=True):
        done_by_day[day] = done_by_day.get(day, 0) + 1
    checkins = {c.date: c for c in DailyCheckin.objects.filter(user=user, date__range=(start, today))}

    daily = []
    for i in range(days):
        day = start + timedelta(days=i)
        c = checkins.get(day)
        done = done_by_day.get(day, 0)
        daily.append({
            "date": day.isoformat(),
            "label": day.strftime("%d/%m"),
            "mood": c.mood if c else None,
            "sleep_hours": c.sleep_hours if c else None,
            "activity_minutes": c.activity_minutes if c else None,
            "habits_done": done,
            "habits_planned": planned,
            "completion_percent": round(done * 100 / planned) if planned else None,
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
        _, created = Notification.objects.get_or_create(
            user=habit.user, kind=Notification.KIND_STREAK_RISK, habit=habit, day=today,
            defaults={
                "title": f"Sắp mất chuỗi {current} ngày",
                "body": f"“{habit.name}” chưa được đánh dấu hôm nay. Làm ngay để giữ chuỗi {current} ngày nhé!",
            },
        )
        created_count += int(created)
    return created_count


def unread_count(user):
    return Notification.objects.filter(user=user, is_read=False).count()
