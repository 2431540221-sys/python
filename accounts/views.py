from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from . import security
from .forms import LoginForm, ProfileForm, RegisterForm, UserPreferencesForm
from .services import admin_statistics, delete_user_data
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
@require_http_methods(["GET", "POST"])
def profile_view(request):
    profile_form = ProfileForm(instance=request.user)
    preferences_form = UserPreferencesForm(instance=request.user)
    if request.method == "POST":
        section = request.POST.get("section")
        if section == "personal":
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Đã cập nhật thông tin cá nhân.")
                return redirect("user_profile")
        elif section == "preferences":
            preferences_form = UserPreferencesForm(request.POST, instance=request.user)
            if preferences_form.is_valid():
                user = preferences_form.save(commit=False)
                user.save(update_fields=["consent_ai", "email_notifications_enabled"])
                messages.success(request, "Đã lưu tùy chỉnh quyền.")
                return redirect("user_profile")
        else:
            messages.error(request, "Yêu cầu cập nhật tài khoản không hợp lệ.")
            return redirect("user_profile")
    return render(request, "accounts/profile.html", {
        "profile_form": profile_form,
        "preferences_form": preferences_form,
    })


def privacy_redirect(request):
    return redirect("user_profile")


@login_required
@require_POST
def delete_data_view(request):
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Hãy tick ô xác nhận trước khi xóa dữ liệu.")
        return redirect("user_profile")
    counts = delete_user_data(request.user)
    messages.success(request, f"Đã xóa {sum(counts.values())} bản ghi dữ liệu cá nhân. Tài khoản vẫn được giữ.")
    return redirect("user_profile")


@login_required
@require_POST
def delete_account_view(request):
    password = request.POST.get("password", "")
    if not authenticate(request, username=request.user.username, password=password):
        messages.error(request, "Mật khẩu không đúng, tài khoản chưa bị xóa.")
        return redirect("user_profile")
    request.user.delete()     # CASCADE: xóa toàn bộ dữ liệu liên quan
    response = redirect("login")
    messages.success(request, "Tài khoản và toàn bộ dữ liệu của bạn đã được xóa.")
    return clear_auth_cookie(response)


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
