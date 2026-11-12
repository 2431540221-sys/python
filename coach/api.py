from django.http import JsonResponse

from accounts.apiutils import ApiError, api

from . import safety
from .models import CoachReport
from .service import ConsentRequired, generate_report


def report_json(report):
    return {
        "week_start": report.week_start.isoformat(), "week_end": report.week_end.isoformat(),
        "summary": report.summary, "patterns": report.patterns, "goals": report.goals,
        "actions": report.actions, "source": report.source,
        "disclaimer": safety.DISCLAIMER,      # luôn kèm disclaimer
    }


@api(methods=("GET", "POST"))
def weekly(request):
    """GET: bản tóm tắt gần nhất. POST: tạo bản tóm tắt tuần mới (cần người dùng đã đồng ý cho AI coach)."""
    if request.method == "GET":
        report = CoachReport.objects.filter(user=request.user).first()
        if report is None:
            raise ApiError(404, "no_report", "Chưa có bản tóm tắt nào. Hãy gọi POST để tạo.")
        return JsonResponse(report_json(report))
    try:
        report = generate_report(request.user)
    except ConsentRequired:
        raise ApiError(403, "consent_required", "Bạn chưa đồng ý cho AI coach đọc số liệu (mục Quyền riêng tư).")
    return JsonResponse(report_json(report), status=201)
