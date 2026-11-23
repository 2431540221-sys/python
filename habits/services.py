"""
Logic nghiệp vụ của Task 2 (tách khỏi views để dễ test; Task 4 và Task 5 dùng lại).

    calculate_streaks(done_dates)   -> (chuỗi hiện tại, chuỗi dài nhất)
    get_habit_stats(habit)          -> dict số liệu 1 thói quen
    send_due_reminders()            -> job nhắc nhở theo giờ
"""
import logging
import json
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.utils import timezone

from .models import BrowserPushSubscription, Habit, HabitLog, Notification

MAX_BACKFILL_DAYS = 60   # cho phép tick bù tối đa 60 ngày trước
logger = logging.getLogger(__name__)


def send_notification_email(notification):
    """Gửi email cho Notification mới đã tạo; không gửi trùng và bỏ qua nếu thiếu email."""
    if not notification.user.email:
        return False
    try:
        sent = send_mail(
            notification.title,
            notification.body,
            settings.DEFAULT_FROM_EMAIL,
            [notification.user.email],
            fail_silently=False,
        )
    except (OSError, ValueError, ImproperlyConfigured, smtplib.SMTPException):
        logger.exception("Không gửi được email thông báo %s cho người dùng %s", notification.pk, notification.user.pk)
        return False
    return bool(sent)


def send_notification_push(notification):
    subscriptions = BrowserPushSubscription.objects.filter(user=notification.user)
    if not subscriptions.exists():
        return 0
    if not settings.VAPID_PRIVATE_KEY:
        logger.warning("Có thiết bị đăng ký push nhưng VAPID_PRIVATE_KEY chưa được cấu hình.")
        return 0

    from pywebpush import WebPushException, webpush

    payload = json.dumps({
        "id": str(notification.pk),
        "title": notification.title,
        "body": notification.body,
        "url": "/notifications/",
    }, ensure_ascii=False)
    sent = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
                ttl=60 * 60,
                timeout=5,
            )
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status_code = response.status_code if response is not None else None
            if status_code in (404, 410):
                subscription.delete()
            logger.warning(
                "Không gửi được push cho subscription %s (HTTP %s)",
                subscription.pk,
                status_code or "không rõ",
                exc_info=True,
            )
        else:
            sent += 1
    return sent


def deliver_notification(notification):
    send_notification_email(notification)
    send_notification_push(notification)


# ---------------------------------------------------------------- Streak
def calculate_streaks(done_dates, today=None):
    """
    Tính (chuỗi hiện tại, chuỗi dài nhất) từ tập các ngày đã hoàn thành.

    - Chuỗi = các ngày liên tiếp, không bỏ ngày nào.
    - Hôm nay CHƯA làm mà hôm qua đã làm -> chuỗi vẫn còn (vẫn còn cả ngày để làm).
    - Bỏ lỡ cả ngày hôm qua và hôm nay chưa làm -> chuỗi hiện tại về 0.
    """
    today = today or timezone.localdate()
    days = sorted(d for d in set(done_dates) if d <= today)
    if not days:
        return 0, 0

    longest = run = 1
    for prev, cur in zip(days, days[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)

    done = set(days)
    cursor = today if today in done else today - timedelta(days=1)
    current = 0
    while cursor in done:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def count_in_week(done_dates, today=None):
    """Số ngày đã hoàn thành trong tuần hiện tại (tuần bắt đầu từ thứ Hai)."""
    today = today or timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    return sum(1 for d in set(done_dates) if week_start <= d <= today)


def get_done_dates(habit):
    return set(habit.logs.values_list("date", flat=True))


def get_habit_stats(habit, today=None):
    today = today or timezone.localdate()
    done_dates = get_done_dates(habit)
    current, longest = calculate_streaks(done_dates, today)
    week_done = count_in_week(done_dates, today)
    goal = habit.streak_goal
    return {
        "done_today": today in done_dates,
        "current_streak": current,
        "longest_streak": longest,
        "total_done": len(done_dates),
        "week_done": week_done,
        "week_target": habit.weekly_target,
        "week_percent": min(100, round(week_done * 100 / habit.weekly_target)),
        "streak_goal": goal,
        "goal_percent": min(100, round(current * 100 / goal)) if goal else None,
        "goal_reached": bool(goal and current >= goal),
        "goal_remaining": max(0, goal - current) if goal else None,
    }


def toggle_day(habit, day=None):
    """Bấm lần 1: đánh dấu xong ngày `day`. Bấm lần 2: bỏ đánh dấu. Trả về True nếu đang là 'đã xong'."""
    day = day or timezone.localdate()
    today = timezone.localdate()
    if day > today:
        raise ValueError("Không thể đánh dấu cho ngày trong tương lai.")
    if (today - day).days > MAX_BACKFILL_DAYS:
        raise ValueError(f"Chỉ được đánh dấu bù tối đa {MAX_BACKFILL_DAYS} ngày trước.")
    _, created = HabitLog.objects.get_or_create(habit=habit, date=day)
    if not created:
        HabitLog.objects.filter(habit=habit, date=day).delete()
    return created


def recent_days(habit, n=28, today=None, done=None):
    """n ngày gần nhất (cũ -> mới) kèm trạng thái xong/chưa, dùng vẽ lưới lịch."""
    today = today or timezone.localdate()
    done = get_done_dates(habit) if done is None else done
    return [
        {"date": d, "done": d in done, "is_today": d == today}
        for d in (today - timedelta(days=i) for i in range(n - 1, -1, -1))
    ]


def habits_with_stats(user, today=None, days=7):
    """Danh sách thói quen đang theo dõi, mỗi cái kèm stats và lưới `days` ngày gần nhất."""
    today = today or timezone.localdate()
    result = []
    for habit in Habit.objects.filter(user=user, is_active=True):
        done = get_done_dates(habit)
        habit.stats = get_habit_stats(habit, today)
        habit.week_grid = recent_days(habit, days, today, done)
        result.append(habit)
    return result


# ---------------------------------------------------------------- Nhắc nhở theo giờ
def send_due_reminders(now=None):
    """
    Tạo nhắc nhở cho mọi thói quen đã đến giờ nhắc mà hôm nay chưa làm. Trả về số nhắc đã tạo.

    Chạy bao nhiêu lần cũng được: mỗi thói quen chỉ nhắc 1 lần/ngày (last_reminded_on +
    ràng buộc UNIQUE của Notification), nên scheduler chạy trùng cũng không nhắc 2 lần.
    """
    now = now or timezone.localtime()
    today = now.date()

    due = (
        Habit.objects.filter(
            is_active=True, reminder_enabled=True,
            reminder_time__isnull=False, reminder_time__lte=now.time(),
        )
        .exclude(last_reminded_on=today)
        .select_related("user")
    )

    sent = 0
    for habit in due:
        done_dates = get_done_dates(habit)
        if today in done_dates:
            continue  # hôm nay đã làm rồi, không cần nhắc

        # "Giành quyền" nhắc bằng 1 câu UPDATE: hai tiến trình chạy trùng thì chỉ một bên thắng.
        claimed = Habit.objects.filter(pk=habit.pk).exclude(last_reminded_on=today).update(last_reminded_on=today)
        if not claimed:
            continue

        current, _ = calculate_streaks(done_dates, today)
        if current > 0:
            body = f"Bạn đang có chuỗi {current} ngày với “{habit.name}”. Làm hôm nay để giữ chuỗi nhé!"
        else:
            body = f"Đến giờ “{habit.name}” rồi. Bắt đầu một chuỗi mới nào!"

        notification, created = Notification.objects.get_or_create(
            user=habit.user, kind=Notification.KIND_REMINDER, habit=habit, day=today,
            defaults={"title": f"Nhắc nhở: {habit.name}", "body": body},
        )
        if created:
            deliver_notification(notification)
        sent += int(created)
    return sent
