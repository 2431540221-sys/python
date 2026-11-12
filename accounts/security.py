"""Chống dò mật khẩu: khóa tạm sau nhiều lần đăng nhập sai."""
from django.core.cache import cache

MAX_FAILS = 5
WINDOW_SECONDS = 15 * 60


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(username, ip):
    return f"loginfail:{(username or '').lower()}:{ip}"


def is_locked(username, ip):
    return cache.get(_key(username, ip), 0) >= MAX_FAILS


def register_failure(username, ip):
    key = _key(username, ip)
    cache.add(key, 0, WINDOW_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, WINDOW_SECONDS)


def clear_failures(username, ip):
    cache.delete(_key(username, ip))
