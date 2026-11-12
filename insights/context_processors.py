from habits.models import Notification


def _section(url_name):
    """Mục đang mở trên thanh điều hướng, suy ra từ tên URL."""
    name = url_name or ""
    if name == "dashboard":
        return "dashboard"
    if name.startswith("habit"):
        return "habits"
    if name in ("checkin", "checkin_delete", "history"):
        return "checkin"
    if name.startswith("journal"):
        return "journal"
    if name.startswith("notification"):
        return "notifications"
    if name.startswith("coach"):
        return "coach"
    if name in ("privacy", "export_data", "delete_data", "delete_account", "demo_data"):
        return "privacy"
    if name == "admin_stats":
        return "admin"
    return ""


def navbar(request):
    """Số thông báo chưa đọc cho chuông + mục đang mở trên thanh điều hướng."""
    match = getattr(request, "resolver_match", None)
    context = {"nav": _section(match.url_name if match else "")}
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        context["unread_count"] = 0
    else:
        context["unread_count"] = Notification.objects.filter(user=user, is_read=False).count()
    return context
