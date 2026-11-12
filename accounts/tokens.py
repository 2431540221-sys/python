"""JWT: tạo và kiểm tra access/refresh token (thư viện PyJWT, thuật toán HS256)."""
import hashlib
from datetime import timedelta
from uuid import uuid4

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone


def _fingerprint(user):
    """Dấu vân tay của mật khẩu: đổi mật khẩu thì mọi token cũ tự vô hiệu."""
    return hashlib.sha256(user.password.encode("utf-8")).hexdigest()[:12]


def _encode(user, token_type, lifetime):
    now = timezone.now()
    payload = {
        "sub": str(user.pk),
        "role": user.role,
        "type": token_type,
        "pv": _fingerprint(user),
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user, lifetime=None):
    return _encode(user, "access", lifetime or timedelta(minutes=settings.JWT_ACCESS_MINUTES))


def create_web_token(user):
    return _encode(user, "access", timedelta(hours=settings.JWT_WEB_HOURS))


def create_refresh_token(user):
    return _encode(user, "refresh", timedelta(days=settings.JWT_REFRESH_DAYS))


def decode_token(token, expected_type="access"):
    """Trả về payload nếu token hợp lệ (chữ ký, hạn dùng, loại token), ngược lại None."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def user_from_token(token, expected_type="access"):
    payload = decode_token(token, expected_type)
    if not payload:
        return None
    User = get_user_model()
    user = User.objects.filter(pk=payload["sub"], is_active=True).first()
    if user is None or payload.get("pv") != _fingerprint(user):
        return None
    return user
