import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from habits.models import BrowserPushSubscription, Notification
from habits.services import habits_with_stats
from tracking.models import DailyCheckin

from .services import (
    create_streak_risk_notifications, create_wellbeing_trend_notifications,
    period_stats, streak_risks,
)

MILESTONES = (3, 7, 14, 21, 30, 60, 100)


def _sprout_stage(streak):
    """Cây Mầm lớn dần theo chuỗi tốt nhất: 0 hạt giống, 1 mầm, 2 hai lá, 3 cây non, 4 ra hoa."""
    if streak >= 21:
        return 4
    if streak >= 7:
        return 3
    if streak >= 3:
        return 2
    return 1 if streak >= 1 else 0


@login_required
def dashboard(request):
    create_streak_risk_notifications(user=request.user)   # kiểm tra ngay khi mở dashboard
    create_wellbeing_trend_notifications(user=request.user)
    today = timezone.localdate()
    habits = habits_with_stats(request.user, today)
    best = max((h.stats["current_streak"] for h in habits), default=0)
    next_milestone = next((m for m in MILESTONES if m > best), None)
    week = period_stats(request.user, "week", today)["summary"]
    recent = Notification.objects.filter(user=request.user)[:4]
    return render(request, "insights/dashboard.html", {
        "habits": habits,
        "done_today": sum(1 for h in habits if h.stats["done_today"]),
        "best_streak": best,
        "sprout_stage": _sprout_stage(best),
        "next_milestone": next_milestone,
        "days_to_milestone": (next_milestone - best) if next_milestone else None,
        "risks": streak_risks(request.user, today),
        "week": week,
        "checked_in_today": DailyCheckin.objects.filter(user=request.user, date=today).exists(),
        "recent_notifications": recent,
    })


@login_required
def notifications(request):
    create_streak_risk_notifications(user=request.user)
    items = Notification.objects.filter(user=request.user).select_related("habit")[:100]
    return render(request, "insights/notifications.html", {
        "items": items,
        "vapid_public_key": settings.VAPID_PUBLIC_KEY,
        "has_push_subscription": BrowserPushSubscription.objects.filter(user=request.user).exists(),
    })


@login_required
@require_POST
def notifications_read(request):
    pk = request.POST.get("pk")
    qs = Notification.objects.filter(user=request.user, is_read=False)
    if pk:
        qs = qs.filter(pk=get_object_or_404(Notification, pk=pk, user=request.user).pk)
    qs.update(is_read=True)
    return redirect("notifications")


def service_worker(request):
    worker = Path(settings.BASE_DIR, "static", "js", "service-worker.js").read_text(encoding="utf-8")
    response = HttpResponse(worker, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def _validated_push_endpoint(endpoint):
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        return False
    try:
        URLValidator(schemes=["https"])(endpoint)
        parsed = urlsplit(endpoint)
        host = parsed.hostname
        parsed.port
    except (ValidationError, ValueError):
        return False
    if not host or parsed.username or parsed.password or host == "localhost" or host.endswith((".localhost", ".local")):
        return False
    try:
        if not ipaddress.ip_address(host).is_global:
            return False
    except ValueError:
        if "." not in host:
            return False
    return True


@login_required
@require_http_methods(["POST", "DELETE"])
def push_subscription(request):
    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_PRIVATE_KEY:
        return JsonResponse({"error": "push_not_configured"}, status=503)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    endpoint = data.get("endpoint") if isinstance(data, dict) else None
    if not _validated_push_endpoint(endpoint):
        return JsonResponse({"error": "invalid_endpoint"}, status=400)

    if request.method == "DELETE":
        BrowserPushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return JsonResponse({"deleted": True})

    keys = data.get("keys")
    p256dh = keys.get("p256dh") if isinstance(keys, dict) else None
    auth = keys.get("auth") if isinstance(keys, dict) else None
    if not isinstance(p256dh, str) or not p256dh or len(p256dh) > 200:
        return JsonResponse({"error": "invalid_subscription"}, status=400)
    if not isinstance(auth, str) or not auth or len(auth) > 100:
        return JsonResponse({"error": "invalid_subscription"}, status=400)

    subscription = BrowserPushSubscription.objects.filter(endpoint=endpoint).first()
    if subscription and subscription.user_id != request.user.pk:
        return JsonResponse({"error": "subscription_in_use"}, status=409)
    if subscription is None:
        BrowserPushSubscription.objects.create(
            user=request.user, endpoint=endpoint, p256dh=p256dh, auth=auth,
        )
    else:
        subscription.p256dh = p256dh
        subscription.auth = auth
        subscription.save(update_fields=["p256dh", "auth", "updated_at"])
    return JsonResponse({"subscribed": True})
