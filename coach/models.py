from django.conf import settings
from django.db import models

from dbsync.base import SyncModel


class CoachReport(SyncModel):
    """Bản tóm tắt tuần do AI coach (hoặc bộ luật dự phòng) tạo ra cho một người dùng."""

    SOURCE_RULES = "rules"
    SOURCE_LLM = "llm"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_reports")
    week_start = models.DateField()
    week_end = models.DateField()
    summary = models.TextField()
    patterns = models.JSONField(default=list)    # các mẫu hình tiêu cực cần lưu ý
    goals = models.JSONField(default=list)       # mục tiêu nhỏ gợi ý
    actions = models.JSONField(default=list)     # hành động nhẹ nhàng, an toàn
    source = models.CharField(max_length=10, default=SOURCE_RULES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_end", "-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user", "week_end"], name="one_report_per_user_per_week_end")]

    def sync_identity(self):
        return f"{self.user.sync_id}:{self.week_end.isoformat()}"

    def __str__(self):
        return f"Báo cáo {self.week_start} - {self.week_end}"
