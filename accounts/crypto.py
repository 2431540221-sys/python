"""Mã hóa nội dung journal bằng Fernet (AES-128-CBC + HMAC), khóa lấy từ settings."""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

DECRYPT_FAILED = "[Không giải mã được nội dung này]"


@lru_cache(maxsize=1)
def _fernet():
    raw = settings.JOURNAL_ENCRYPTION_KEY.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())  # 32 byte -> khóa Fernet
    return Fernet(key)


def encrypt_text(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return DECRYPT_FAILED


class EncryptedTextField(models.TextField):
    """Trong code dùng như TextField bình thường; trong database luôn là chuỗi đã mã hóa."""

    def get_db_prep_save(self, value, connection):
        value = super().get_db_prep_save(value, connection)
        return encrypt_text(value) if value else value

    def from_db_value(self, value, expression, connection):
        return decrypt_text(value) if value else value
