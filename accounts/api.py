from django.contrib.auth import authenticate
from django.http import JsonResponse

from . import security
from .apiutils import ApiError, api, form_errors, read_json
from .forms import RegisterForm
from .services import admin_statistics, delete_user_data
from .tokens import create_access_token, create_refresh_token, user_from_token


def user_json(user):
    return {
        "id": user.pk, "username": user.username, "email": user.email,
        "role": user.role, "consent_ai": user.consent_ai,
    }


def token_pair(user):
    return {"access": create_access_token(user), "refresh": create_refresh_token(user), "token_type": "Bearer"}


@api(methods=("POST",), auth=False)
def register(request):
    data = read_json(request)
    password = data.get("password", "")
    form = RegisterForm({
        "username": data.get("username", ""),
        "email": data.get("email", ""),
        "password1": password,
        "password2": password,
        "consent_ai": bool(data.get("consent_ai", False)),
    })
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    user = form.save()
    return JsonResponse({"user": user_json(user), **token_pair(user)}, status=201)


@api(methods=("POST",), auth=False)
def login(request):
    data = read_json(request)
    username, password = data.get("username", ""), data.get("password", "")
    ip = security.client_ip(request)
    if security.is_locked(username, ip):
        raise ApiError(429, "too_many_attempts", "Sai quá nhiều lần, thử lại sau 15 phút.")
    user = authenticate(request, username=username, password=password)
    if user is None:
        security.register_failure(username, ip)
        raise ApiError(401, "invalid_credentials", "Sai tên đăng nhập hoặc mật khẩu.")
    security.clear_failures(username, ip)
    return JsonResponse({"user": user_json(user), **token_pair(user)})


@api(methods=("POST",), auth=False)
def refresh(request):
    user = user_from_token(read_json(request).get("refresh", ""), expected_type="refresh")
    if user is None:
        raise ApiError(401, "invalid_token", "Refresh token không hợp lệ hoặc đã hết hạn.")
    return JsonResponse({"access": create_access_token(user), "token_type": "Bearer"})


@api(methods=("GET", "DELETE"))
def me(request):
    """GET: thông tin của tôi. DELETE: xóa tài khoản và toàn bộ dữ liệu (cần gửi password)."""
    if request.method == "GET":
        return JsonResponse(user_json(request.user))
    password = read_json(request).get("password", "")
    if not authenticate(request, username=request.user.username, password=password):
        raise ApiError(403, "wrong_password", "Cần gửi đúng mật khẩu để xóa tài khoản.")
    request.user.delete()
    return JsonResponse({"deleted": True, "detail": "Tài khoản và toàn bộ dữ liệu đã bị xóa."})


@api(methods=("DELETE",))
def delete_my_data(request):
    """Xóa dữ liệu cá nhân nhưng giữ tài khoản."""
    return JsonResponse({"deleted": delete_user_data(request.user)})


@api(methods=("GET",), roles=("admin",))
def admin_stats(request):
    return JsonResponse(admin_statistics())
