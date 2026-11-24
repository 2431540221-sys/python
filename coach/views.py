from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import llm, safety
from .models import CoachReport
from .service import ConsentRequired, answer_question, generate_report

CHAT_HISTORY_KEY = "coach_chat_history"
MAX_CHAT_TURNS = 8


@login_required
def coach_page(request):
    return render(request, "coach/coach.html", {
        "report": CoachReport.objects.filter(user=request.user).first(),
        "disclaimer": safety.DISCLAIMER,
        "using_llm": llm.llm_available(),
        "chat_history": request.session.get(CHAT_HISTORY_KEY, []),
    })


@login_required
@require_POST
def coach_generate(request):
    try:
        generate_report(request.user)
    except ConsentRequired:
        messages.error(request, "Bạn cần bật quyền cho AI Coach trong phần Tài khoản trước.")
        return redirect("user_profile")
    messages.success(request, "Đã tạo bản tóm tắt tuần.")
    return redirect("coach")


@login_required
@require_POST
def coach_ask(request):
    question = request.POST.get("question", "").strip()[:500]
    if not question:
        messages.error(request, "Hãy nhập câu hỏi trước.")
        return redirect("coach")
    history = request.session.get(CHAT_HISTORY_KEY, [])
    try:
        answer = answer_question(request.user, question, history)
    except ConsentRequired:
        messages.error(request, "Bạn cần bật quyền cho AI Coach trong phần Tài khoản trước.")
        return redirect("user_profile")
    history.append({"question": question, **answer})
    request.session[CHAT_HISTORY_KEY] = history[-MAX_CHAT_TURNS:]
    return redirect("coach")


@login_required
@require_POST
def coach_clear_chat(request):
    request.session.pop(CHAT_HISTORY_KEY, None)
    return redirect("coach")
