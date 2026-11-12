from django.conf import settings

from .tokens import user_from_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class JWTAuthMiddleware:
    """
    Đọc JWT và gán request.user.

    - Header "Authorization: Bearer <token>": dùng cho API (mọi phương thức).
    - Cookie của trang web: dùng cho trang web (có CSRF bảo vệ) và các API chỉ-đọc (GET)
      để biểu đồ trên dashboard gọi được API. API ghi dữ liệu (POST/PUT/DELETE) bắt buộc
      dùng Bearer, nên không thể bị tấn công CSRF qua cookie.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token, source = self._extract(request)
        if token:
            user = user_from_token(token)
            if user is not None:
                request.user = user
                request.jwt_source = source
        return self.get_response(request)

    @staticmethod
    def _extract(request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header[:7].lower() == "bearer ":
            return header[7:].strip(), "bearer"
        cookie = request.COOKIES.get(settings.JWT_COOKIE_NAME)
        if cookie:
            is_api = request.path.startswith("/api/")
            if not is_api or request.method in SAFE_METHODS:
                return cookie, "cookie"
        return None, None
