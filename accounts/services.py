"""Xuất / xóa dữ liệu cá nhân và thống kê ẩn danh cho admin (Task 1)."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.utils import timezone


def export_user_data(user):
    """Toàn bộ dữ liệu của chính người dùng (kể cả journal đã được giải mã)."""
    habits = []
    for habit in user.habits.all().prefetch_related("logs"):
        habits.append({
            "name": habit.name,
            "description": habit.description,
            "weekly_target": habit.weekly_target,
            "streak_goal": habit.streak_goal,
            "reminder_time": habit.reminder_time.strftime("%H:%M") if habit.reminder_time else None,
            "completed_dates": sorted(log.date.isoformat() for log in habit.logs.all()),
        })
    return {
        "exported_at": timezone.now().isoformat(),
        "profile": {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "consent_ai": user.consent_ai,
            "date_joined": user.date_joined.isoformat(),
        },
        "habits": habits,
        "checkins": [
            {
                "date": c.date.isoformat(), "mood": c.mood, "sleep_hours": c.sleep_hours,
                "activity_type": c.activity_type, "activity_minutes": c.activity_minutes, "note": c.note,
            }
            for c in user.checkins.all()
        ],
        "journals": [
            {
                "title": j.title, "content": j.content, "tags": j.tags,
                "created_at": j.created_at.isoformat(),
            }
            for j in user.journals.all()
        ],
        "notifications": [
            {"kind": n.kind, "title": n.title, "body": n.body, "created_at": n.created_at.isoformat()}
            for n in user.notifications.all()
        ],
        "coach_reports": [
            {
                "week_end": r.week_end.isoformat(), "summary": r.summary,
                "patterns": r.patterns, "goals": r.goals, "actions": r.actions, "source": r.source,
            }
            for r in user.coach_reports.all()
        ],
    }


def delete_user_data(user):
    """Xóa dữ liệu cá nhân nhưng giữ lại tài khoản. Trả về số bản ghi đã xóa theo nhóm."""
    counts = {
        "habits": user.habits.count(),
        "checkins": user.checkins.count(),
        "journals": user.journals.count(),
        "notifications": user.notifications.count(),
        "coach_reports": user.coach_reports.count(),
    }
    user.habits.all().delete()          # kéo theo habit logs (CASCADE)
    user.checkins.all().delete()
    user.journals.all().delete()
    user.notifications.all().delete()
    user.coach_reports.all().delete()
    return counts


def admin_statistics():
    """
    Thống kê TỔNG HỢP và ẨN DANH cho quản trị viên: chỉ có con số, không có tên đăng nhập,
    email, nội dung journal hay dữ liệu từng người. Nếu quá ít người dùng thì không hiển thị
    (để không suy ra được dữ liệu của một cá nhân).
    """
    from habits.models import Habit, HabitLog
    from tracking.models import DailyCheckin, JournalEntry

    User = get_user_model()
    total_users = User.objects.count()
    minimum = settings.MIN_USERS_FOR_ADMIN_STATS
    if total_users < minimum:
        return {
            "available": False,
            "min_users": minimum,
            "detail": f"Cần ít nhất {minimum} người dùng để hiển thị thống kê ẩn danh.",
        }

    today = timezone.localdate()
    since7, since30 = today - timedelta(days=6), today - timedelta(days=29)

    active_ids = set(
        DailyCheckin.objects.filter(date__gte=since7).values_list("user_id", flat=True)
    ) | set(
        HabitLog.objects.filter(date__gte=since7).values_list("habit__user_id", flat=True)
    )
    checkins30 = DailyCheckin.objects.filter(date__gte=since30)
    averages = checkins30.aggregate(mood=Avg("mood"), sleep=Avg("sleep_hours"))
    mood_dist = {str(i): 0 for i in range(1, 6)}
    for row in checkins30.values("mood").annotate(n=Count("id")):
        mood_dist[str(row["mood"])] = row["n"]
    consent_count = User.objects.filter(consent_ai=True).count()
    habits_total = Habit.objects.count()

    def rnd(value, digits=2):
        return round(value, digits) if value is not None else None

    return {
        "available": True,
        "generated_at": timezone.now().isoformat(),
        "users": {
            "total": total_users,
            "active_last_7_days": len(active_ids),
            "new_last_30_days": User.objects.filter(date_joined__date__gte=since30).count(),
            "consent_ai_percent": round(consent_count * 100 / total_users),
        },
        "habits": {
            "total": habits_total,
            "active": Habit.objects.filter(is_active=True).count(),
            "completions_last_7_days": HabitLog.objects.filter(date__gte=since7).count(),
            "avg_habits_per_user": rnd(habits_total / total_users, 1),
        },
        "checkins_last_30_days": {
            "count": checkins30.count(),
            "avg_mood": rnd(averages["mood"]),
            "avg_sleep_hours": rnd(averages["sleep"]),
            "mood_distribution": mood_dist,
        },
        "journals": {"total_entries": JournalEntry.objects.count()},   # chỉ đếm, không đọc nội dung
        "note": "Số liệu tổng hợp ẩn danh: không chứa tên đăng nhập, email hay nội dung journal.",
    }
