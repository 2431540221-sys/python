from django.http import JsonResponse
from django.utils import timezone

from accounts.apiutils import ApiError, api
from habits.models import Notification

from .services import PERIODS, create_streak_risk_notifications, period_stats


@api(methods=("GET",))
def stats(request):
    """GET /api/stats/?period=week|month  -> số liệu của chính người dùng đang đăng nhập."""
    period = request.GET.get("period", "week")
    if period not in PERIODS:
        raise ApiError(400, "invalid_period", "period phải là week hoặc month.")
    return JsonResponse(period_stats(request.user, period))


@api(methods=("GET",))
def notifications(request):
    create_streak_risk_notifications(user=request.user)       # kiểm tra ngay khi người dùng mở
    items = Notification.objects.filter(user=request.user)[:50]
    return JsonResponse({
        "unread": Notification.objects.filter(user=request.user, is_read=False).count(),
        "notifications": [
            {"id": n.pk, "kind": n.kind, "title": n.title, "body": n.body, "is_read": n.is_read,
             "created_at": timezone.localtime(n.created_at).isoformat()}
            for n in items
        ],
    })
