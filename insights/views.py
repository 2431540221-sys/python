from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from habits.models import Notification
from habits.services import habits_with_stats
from tracking.models import DailyCheckin

from .services import create_streak_risk_notifications, period_stats, streak_risks

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
    return render(request, "insights/notifications.html", {"items": items})


@login_required
@require_POST
def notifications_read(request):
    pk = request.POST.get("pk")
    qs = Notification.objects.filter(user=request.user, is_read=False)
    if pk:
        qs = qs.filter(pk=get_object_or_404(Notification, pk=pk, user=request.user).pk)
    qs.update(is_read=True)
    return redirect("notifications")
