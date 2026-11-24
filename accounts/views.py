import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import security
from .forms import LoginForm, RegisterForm
from .sample_data import seed_user_data
from .services import admin_statistics, delete_user_data, export_user_data
from .tokens import create_web_token


def set_auth_cookie(response, user):
    response.set_cookie(
        settings.JWT_COOKIE_NAME,
        create_web_token(user),
        max_age=settings.JWT_WEB_HOURS * 3600,
        httponly=True,               # JavaScript không đọc được token
        secure=settings.JWT_COOKIE_SECURE,
        samesite="Lax",
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie(settings.JWT_COOKIE_NAME)
    return response


def home(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, "Chào mừng bạn đến với Mầm! Hãy tạo thói quen đầu tiên nhé.")
        return set_auth_cookie(redirect("habit_list"), user)
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST":
        username = request.POST.get("username", "")
        ip = security.client_ip(request)
        if security.is_locked(username, ip):
            form.add_error(None, "Bạn nhập sai quá nhiều lần. Hãy thử lại sau 15 phút.")
        elif form.is_valid():
            security.clear_failures(username, ip)
            target = request.POST.get("next") or request.GET.get("next") or ""
            if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
                target = ""
            return set_auth_cookie(redirect(target or "dashboard"), form.get_user())
        else:
            security.register_failure(username, ip)
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    return clear_auth_cookie(redirect("login"))


@login_required
def privacy_view(request):
    if request.method == "POST":
        request.user.consent_ai = "consent_ai" in request.POST
        request.user.save(update_fields=["consent_ai"])
        messages.success(request, "Đã cập nhật lựa chọn về AI coach.")
        return redirect("privacy")
    return render(request, "accounts/privacy.html")


@login_required
def export_view(request):
    payload = json.dumps(export_user_data(request.user), ensure_ascii=False, indent=2)
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="du_lieu_cua_toi.json"'
    return response


@login_required
@require_POST
def delete_data_view(request):
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Hãy tick ô xác nhận trước khi xóa dữ liệu.")
        return redirect("privacy")
    counts = delete_user_data(request.user)
    messages.success(request, f"Đã xóa {sum(counts.values())} bản ghi dữ liệu cá nhân. Tài khoản vẫn được giữ.")
    return redirect("privacy")


@login_required
@require_POST
def delete_account_view(request):
    password = request.POST.get("password", "")
    if not authenticate(request, username=request.user.username, password=password):
        messages.error(request, "Mật khẩu không đúng, tài khoản chưa bị xóa.")
        return redirect("privacy")
    request.user.delete()     # CASCADE: xóa toàn bộ dữ liệu liên quan
    response = redirect("login")
    messages.success(request, "Tài khoản và toàn bộ dữ liệu của bạn đã được xóa.")
    return clear_auth_cookie(response)


@login_required
@require_POST
def sample_data_view(request):
    seed_user_data(request.user, 30)
    messages.success(request, "Đã nạp dữ liệu mẫu 30 ngày vào tài khoản của bạn.")
    return redirect("dashboard")


@login_required
def admin_stats_view(request):
    if not request.user.is_admin_role:
        raise PermissionDenied
    stats = admin_statistics()
    mood_rows = []
    if stats.get("available"):
        dist = stats["checkins_last_30_days"]["mood_distribution"]
        biggest = max(dist.values(), default=0) or 1
        mood_rows = [(level, n, round(n * 100 / biggest)) for level, n in dist.items()]
    return render(request, "accounts/admin_stats.html", {"stats": stats, "mood_rows": mood_rows})
