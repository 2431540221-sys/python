"""
Task 2 - mô hình dữ liệu thói quen.

    User 1 ──< Habit 1 ──< HabitLog        (mỗi dòng HabitLog = 1 ngày đã hoàn thành)
    User 1 ──< Notification                (nhắc nhở, cảnh báo sắp mất chuỗi, gợi ý từ AI coach)
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Habit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habits")
    name = models.CharField("Tên thói quen", max_length=100)
    description = models.CharField("Mô tả", max_length=255, blank=True)
    weekly_target = models.PositiveSmallIntegerField(
        "Mục tiêu mỗi tuần (số ngày)", default=7,
        validators=[MinValueValidator(1), MaxValueValidator(7)],
    )
    streak_goal = models.PositiveSmallIntegerField(
        "Mục tiêu chuỗi (số ngày liên tiếp)", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
    )
    reminder_enabled = models.BooleanField("Bật nhắc nhở", default=False)
    reminder_time = models.TimeField("Giờ nhắc", null=True, blank=True)
    last_reminded_on = models.DateField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.reminder_enabled and not self.reminder_time:
            raise ValidationError({"reminder_time": "Hãy chọn giờ nhắc khi bật nhắc nhở."})


class HabitLog(models.Model):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField(default=timezone.localdate)
    note = models.CharField("Ghi chú", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["habit", "date"], name="one_log_per_habit_per_day")
        ]

    def __str__(self):
        return f"{self.habit.name} - {self.date}"


class Notification(models.Model):
    KIND_REMINDER = "reminder"
    KIND_STREAK_RISK = "streak_risk"
    KIND_COACH = "coach"
    KIND_CHOICES = [
        (KIND_REMINDER, "Nhắc nhở"),
        (KIND_STREAK_RISK, "Sắp mất chuỗi"),
        (KIND_COACH, "AI coach"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_REMINDER)
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=300, blank=True)
    day = models.DateField(default=timezone.localdate)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # mỗi loại thông báo chỉ tạo 1 lần/ngày cho mỗi thói quen
            models.UniqueConstraint(fields=["user", "kind", "habit", "day"], name="one_notification_per_kind_habit_day")
        ]

    def __str__(self):
        return self.title
