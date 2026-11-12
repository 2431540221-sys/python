"""Task 3 - check-in tâm trạng/giấc ngủ/hoạt động theo ngày và journal riêng tư (mã hóa)."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.crypto import EncryptedTextField

MOOD_CHOICES = [(1, "Rất tệ"), (2, "Không ổn"), (3, "Bình thường"), (4, "Tốt"), (5, "Rất tốt")]

ACTIVITY_CHOICES = [
    ("none", "Hôm nay chưa vận động"),
    ("walking", "Đi bộ"),
    ("running", "Chạy bộ"),
    ("cycling", "Đạp xe"),
    ("gym", "Tập gym"),
    ("yoga", "Yoga / giãn cơ"),
    ("sports", "Chơi thể thao"),
    ("other", "Khác"),
]


class DailyCheckin(models.Model):
    """Một dòng = một ngày của một người (check-in lại trong ngày sẽ cập nhật dòng đó)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkins")
    date = models.DateField(default=timezone.localdate)
    mood = models.PositiveSmallIntegerField(
        "Tâm trạng", choices=MOOD_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    sleep_hours = models.FloatField(
        "Giờ ngủ đêm qua", default=7, validators=[MinValueValidator(0), MaxValueValidator(24)]
    )
    activity_type = models.CharField("Hoạt động", max_length=20, choices=ACTIVITY_CHOICES, default="none")
    activity_minutes = models.PositiveSmallIntegerField(
        "Số phút vận động", default=0, validators=[MaxValueValidator(1440)]
    )
    note = models.CharField("Ghi chú nhanh", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="one_checkin_per_user_per_day")]

    def __str__(self):
        return f"{self.user_id} - {self.date}"


class JournalEntry(models.Model):
    """Journal riêng tư: chỉ chủ sở hữu xem được, nội dung được mã hóa trong database."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="journals")
    title = models.CharField("Tiêu đề", max_length=200)
    content = EncryptedTextField("Nội dung")
    tags = models.CharField("Thẻ", max_length=200, blank=True, help_text="Cách nhau bằng dấu phẩy")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]
