from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CheckinForm, JournalForm
from .models import DailyCheckin, JournalEntry


@login_required
def checkin(request):
    """Form check-in: mood 1-5, giờ ngủ, hoạt động. Check-in lại cùng ngày thì cập nhật."""
    today = timezone.localdate()
    existing = DailyCheckin.objects.filter(user=request.user, date=today).first()
    if request.method == "POST":
        try:
            target = DailyCheckin.objects.filter(user=request.user, date=request.POST.get("date")).first()
        except Exception:      # ngày gửi lên sai định dạng: để form tự báo lỗi
            target = None
        form = CheckinForm(request.POST, instance=target)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, f"Đã lưu check-in ngày {entry.date:%d/%m/%Y}.")
            return redirect("history")
    else:
        form = CheckinForm(instance=existing, initial={"date": today})
    return render(request, "tracking/checkin.html", {"form": form, "existing": existing, "today": today})


@login_required
def history(request):
    entries = DailyCheckin.objects.filter(user=request.user)[:60]
    return render(request, "tracking/history.html", {"entries": entries})


@login_required
@require_POST
def checkin_delete(request, pk):
    get_object_or_404(DailyCheckin, pk=pk, user=request.user).delete()
    messages.success(request, "Đã xóa check-in.")
    return redirect("history")


# ---------------------------------------------------------------- Journal (chỉ chủ sở hữu)
def _own_entry(request, pk):
    return get_object_or_404(JournalEntry, pk=pk, user=request.user)   # của người khác -> 404


@login_required
def journal_list(request):
    entries = list(JournalEntry.objects.filter(user=request.user))
    q = request.GET.get("q", "").strip().lower()
    if q:   # nội dung được mã hóa trong DB nên lọc ở Python trên dữ liệu của chính người dùng
        entries = [e for e in entries if q in e.title.lower() or q in e.content.lower() or q in e.tags.lower()]
    return render(request, "tracking/journal_list.html", {"entries": entries, "q": q})


@login_required
def journal_create(request):
    form = JournalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.user = request.user
        entry.save()
        messages.success(request, "Đã lưu journal. Nội dung được mã hóa và chỉ mình bạn xem được.")
        return redirect("journal_detail", pk=entry.pk)
    return render(request, "tracking/journal_form.html", {"form": form, "title": "Viết journal mới"})


@login_required
def journal_detail(request, pk):
    return render(request, "tracking/journal_detail.html", {"entry": _own_entry(request, pk)})


@login_required
def journal_update(request, pk):
    entry = _own_entry(request, pk)
    form = JournalForm(request.POST or None, instance=entry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật journal.")
        return redirect("journal_detail", pk=entry.pk)
    return render(request, "tracking/journal_form.html", {"form": form, "title": "Sửa journal", "entry": entry})


@login_required
def journal_delete(request, pk):
    entry = _own_entry(request, pk)
    if request.method == "POST":
        entry.delete()
        messages.success(request, "Đã xóa journal.")
        return redirect("journal_list")
    return render(request, "tracking/journal_confirm_delete.html", {"entry": entry})
