import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Người dùng: thêm vai trò (user/admin) và quyền đồng ý cho AI coach."""

    sync_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sync_updated_at = models.DateTimeField(default=timezone.now, editable=False)

    ROLE_USER = "user"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [(ROLE_USER, "Người dùng"), (ROLE_ADMIN, "Quản trị viên")]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_USER)
    consent_ai = models.BooleanField(
        "Đồng ý cho AI coach đọc số liệu của tôi", default=False
    )
    email_notifications_enabled = models.BooleanField(
        "Nhận thông báo qua email", default=False
    )

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ROLE_ADMIN
        from dbsync.base import SyncModel

        SyncModel.prepare_sync_save(self, kwargs)
        super().save(*args, **kwargs)

    def sync_identity(self):
        return self.username

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN
