from django.conf import settings
from django.db import models
from django.utils import timezone


class DailyWellbeingIndex(models.Model):
    """Chỉ số wellbeing tổng hợp theo ngày (thang 0-100)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wellbeing_indices")
    date = models.DateField(default=timezone.localdate)
    score = models.FloatField(null=True, blank=True)
    mood_score = models.FloatField(null=True, blank=True)
    sleep_score = models.FloatField(null=True, blank=True)
    activity_score = models.FloatField(null=True, blank=True)
    habit_score = models.FloatField(null=True, blank=True)
    coverage_percent = models.PositiveSmallIntegerField(default=0)
    source_fingerprint = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="one_wellbeing_index_per_day")
        ]

