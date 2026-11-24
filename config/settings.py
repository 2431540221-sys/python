"""
Mầm Wellbeing - cấu hình chung cho cả 5 task.

Biến môi trường quan trọng khi deploy (xem README.md):
    SECRET_KEY, DEBUG, DATABASE_URL, JOURNAL_ENCRYPTION_KEY,
    COACH_SERVICE_URL, INTERNAL_SERVICE_TOKEN (tùy chọn)
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------- Cơ bản
DEBUG = env_bool("DEBUG", True)

SECRET_KEY = os.environ.get("SECRET_KEY") or (
    "dev-only-insecure-key-please-change-before-deploying-0123456789" if DEBUG else None
)
if not SECRET_KEY:
    raise ImproperlyConfigured("Hãy đặt biến môi trường SECRET_KEY khi DEBUG=0.")

_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
for _var in ("RENDER_EXTERNAL_HOSTNAME", "RAILWAY_PUBLIC_DOMAIN"):
    if os.environ.get(_var):
        _hosts.append(os.environ[_var])
if DEBUG:
    _hosts += ["localhost", "127.0.0.1", "[::1]"]
ALLOWED_HOSTS = _hosts
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in _hosts if h not in ("localhost", "127.0.0.1", "[::1]")
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 5 app, mỗi app ứng với 1 task của nhóm
    "accounts",   # Task 1: tài khoản, JWT, phân quyền, bảo vệ dữ liệu cá nhân
    "habits",     # Task 2: thói quen, streak, nhắc nhở
    "tracking",   # Task 3: check-in tâm trạng/giấc ngủ/hoạt động và journal riêng tư
    "insights",   # Task 4: dashboard xu hướng, thông báo
    "coach",      # Task 5: AI coach nhẹ
]
# Lưu ý: cố ý KHÔNG bật django.contrib.admin để quản trị viên không thể mở
# bảng dữ liệu cá nhân của người dùng. Admin chỉ xem thống kê ẩn danh (/admin-stats/).

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.JWTAuthMiddleware",   # đọc JWT -> request.user
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "insights.context_processors.navbar",
            ],
        },
    },
]

# ---------------------------------------------------------------- Database
if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.config(conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# Mật khẩu được băm bằng PBKDF2-SHA256 (mặc định của Django), không lưu dạng chữ thường.

if sys.argv[1:2] == ["test"]:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]   # chỉ để chạy test nhanh

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- Static
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---------------------------------------------------------------- JWT (Task 1)
JWT_ALGORITHM = "HS256"
JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY") or SECRET_KEY
JWT_ACCESS_MINUTES = int(os.environ.get("JWT_ACCESS_MINUTES", "60"))   # token cho API
JWT_REFRESH_DAYS = int(os.environ.get("JWT_REFRESH_DAYS", "7"))
JWT_WEB_HOURS = int(os.environ.get("JWT_WEB_HOURS", "8"))              # token trong cookie của trang web
JWT_COOKIE_NAME = "mam_access"

# Khóa mã hóa nội dung journal (Task 1 + Task 3). Nên đặt riêng, và GIỮ CỐ ĐỊNH:
# mất khóa này thì journal đã lưu sẽ không giải mã được.
JOURNAL_ENCRYPTION_KEY = os.environ.get("JOURNAL_ENCRYPTION_KEY") or SECRET_KEY

# Admin chỉ thấy thống kê khi có ít nhất ngần này người dùng (tránh suy ra từng người)
MIN_USERS_FOR_ADMIN_STATS = int(os.environ.get("MIN_USERS_FOR_ADMIN_STATS", "3"))

# ---------------------------------------------------------------- Nhắc nhở / thông báo (Task 2, 4)
ENABLE_SCHEDULER = env_bool("ENABLE_SCHEDULER", True)
STREAK_RISK_FROM_HOUR = int(os.environ.get("STREAK_RISK_FROM_HOUR", "18"))  # từ 18h mới báo "sắp mất streak"
WELLBEING_NUDGE_FROM_HOUR = int(os.environ.get("WELLBEING_NUDGE_FROM_HOUR", "20"))
WELLBEING_NUDGE_DROP_POINTS = int(os.environ.get("WELLBEING_NUDGE_DROP_POINTS", "15"))

# ---------------------------------------------------------------- Email (nhắc nhở, streak, AI coach)
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Mầm Wellbeing <no-reply@mam-wellbeing.local>")

# ---------------------------------------------------------------- Web Push
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")

# ---------------------------------------------------------------- AI coach (Task 5)
COACH_SERVICE_URL = os.environ.get("COACH_SERVICE_URL", "").rstrip("/")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
COACH_SERVICE_TIMEOUT = int(os.environ.get("COACH_SERVICE_TIMEOUT", "25"))

# ---------------------------------------------------------------- Bảo mật khi deploy
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SECURE_CONTENT_TYPE_NOSNIFF = True
JWT_COOKIE_SECURE = not DEBUG

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
