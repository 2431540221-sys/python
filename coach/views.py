from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import llm, safety
from .models import CoachReport
from .service import ConsentRequired, answer_question, generate_report


@login_required
def coach_page(request):
    return render(request, "coach/coach.html", {
        "report": CoachReport.objects.filter(user=request.user).first(),
        "disclaimer": safety.DISCLAIMER,
        "using_llm": llm.llm_available(),
        "answer": request.session.pop("coach_answer", None),
    })


@login_required
@require_POST
def coach_generate(request):
    try:
        generate_report(request.user)
    except ConsentRequired:
        messages.error(request, "Bạn cần bật quyền cho AI coach trong mục Quyền riêng tư trước.")
        return redirect("privacy")
    messages.success(request, "Đã tạo bản tóm tắt tuần.")
    return redirect("coach")


@login_required
@require_POST
def coach_ask(request):
    question = request.POST.get("question", "").strip()[:500]
    if not question:
        messages.error(request, "Hãy nhập câu hỏi trước.")
        return redirect("coach")
    try:
        request.session["coach_answer"] = {"question": question, **answer_question(request.user, question)}
    except ConsentRequired:
        messages.error(request, "Bạn cần bật quyền cho AI coach trong mục Quyền riêng tư trước.")
        return redirect("privacy")
    return redirect("coach")
