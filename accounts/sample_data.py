"""Tạo dữ liệu mẫu cho tài khoản hiện tại."""
import random
from datetime import timedelta

from django.utils import timezone

ACTIVITIES = ["walking", "running", "yoga", "gym", "cycling"]


def seed_user_data(user, days=30):
    """Thêm thói quen, check-in `days` ngày và vài journal cho `user`. Chạy lại không bị nhân đôi."""
    from habits.models import Habit, HabitLog
    from tracking.models import DailyCheckin, JournalEntry

    rng = random.Random(user.pk)
    today = timezone.localdate()

    # Mỗi thói quen minh họa một tình huống streak khác nhau
    plans = [
        ("Đi bộ 20 phút", "streak đang chạy, đã làm hôm nay", range(0, 10), None),
        ("Uống đủ 2 lít nước", "hôm nay chưa làm: sắp mất chuỗi", range(1, 8), None),
        ("Đọc sách 15 phút", "đã bỏ lỡ hôm qua: chuỗi về 0", range(2, 9), None),
        ("Ngủ trước 23h", "làm không đều", None, 0.6),
    ]
    for name, description, offsets, probability in plans:
        habit, _ = Habit.objects.get_or_create(
            user=user, name=name,
            defaults={"description": description, "weekly_target": 7, "streak_goal": 21,
                      "reminder_enabled": True, "reminder_time": "20:00"},
        )
        for offset in range(days):
            if offsets is not None:
                done = offset in offsets
            else:
                done = rng.random() < probability
            if done:
                HabitLog.objects.get_or_create(habit=habit, date=today - timedelta(days=offset))

    for offset in range(days):
        day = today - timedelta(days=offset)
        mood = max(1, min(5, round(rng.gauss(3.6, 1.0))))
        sleep = round(max(3.5, min(10, rng.gauss(7, 1.2))) * 2) / 2
        active = rng.random() < 0.6
        DailyCheckin.objects.update_or_create(
            user=user, date=day,
            defaults={
                "mood": mood, "sleep_hours": sleep,
                "activity_type": rng.choice(ACTIVITIES) if active else "none",
                "activity_minutes": rng.choice([15, 20, 30, 45, 60]) if active else 0,
                "note": "",
            },
        )

    entries = [
        ("Một ngày nhiều deadline", "Hôm nay mình hơi quá tải vì dồn bài tập, nhưng chia nhỏ việc ra thì thấy nhẹ hơn.", "học tập"),
        ("Đi bộ buổi tối", "Đi bộ 20 phút quanh khu nhà giúp đầu óc thoáng hẳn. Mình muốn giữ thói quen này.", "sức khỏe"),
        ("Cuối tuần", "Cuối tuần mình ngủ đủ giấc và đọc được 30 trang sách.", "cuộc sống"),
    ]
    for title, content, tags in entries:
        if not JournalEntry.objects.filter(user=user, title=title).exists():
            JournalEntry.objects.create(user=user, title=f"{title}", content=f"[{user.username}] {content}", tags=tags)
    return {"habits": len(plans), "checkins": days, "journals": len(entries)}
