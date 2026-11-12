import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


class ApiError(Exception):
    def __init__(self, status, code, detail=""):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail


def read_json(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "invalid_json", "Nội dung gửi lên không phải JSON hợp lệ.")
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "JSON phải là một object.")
    return data


def api(methods=("GET",), auth=True, roles=None):
    """Decorator cho API: kiểm tra phương thức, đăng nhập (JWT), vai trò và gom lỗi về JSON."""

    def decorator(fn):
        @csrf_exempt
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({"error": "method_not_allowed"}, status=405)
            if auth:
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {"error": "unauthorized", "detail": "Cần gửi header Authorization: Bearer <access_token>."},
                        status=401,
                    )
                if roles and request.user.role not in roles:
                    return JsonResponse(
                        {"error": "forbidden", "detail": "Vai trò của bạn không được phép."}, status=403
                    )
            try:
                return fn(request, *args, **kwargs)
            except ApiError as exc:
                return JsonResponse({"error": exc.code, "detail": exc.detail}, status=exc.status)

        return wrapper

    return decorator


def form_errors(form):
    return {field: [str(e) for e in errs] for field, errs in form.errors.items()}
