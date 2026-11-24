from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CheckinForm, JournalForm
from .models import DailyCheckin, JournalEntry


@login_required
def checkin(request):
    """Cho phép tạo tối đa một check-in trong ngày hiện tại."""
    today = timezone.localdate()
    existing = DailyCheckin.objects.filter(user=request.user, date=today).first()
    if request.method == "POST":
        raw_date = request.POST.get("date")
        if raw_date:
            try:
                submitted_date = date.fromisoformat(raw_date)
            except ValueError:
                messages.error(request, "Ngày check-in không hợp lệ.")
                return redirect("checkin")
            if submitted_date != today:
                messages.error(request, "Chỉ được check-in cho ngày hôm nay.")
                return redirect("checkin")
        if existing:
            messages.info(request, "Bạn đã check-in hôm nay rồi.")
            return redirect("history")

        form = CheckinForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.date = today
            try:
                with transaction.atomic():
                    entry.save()
            except IntegrityError:
                messages.info(request, "Bạn đã check-in hôm nay rồi.")
                return redirect("history")
            messages.success(request, f"Đã lưu check-in ngày {entry.date:%d/%m/%Y}.")
            return redirect("history")
    else:
        form = CheckinForm()
    return render(request, "tracking/checkin.html", {"form": form, "existing": existing, "today": today})


@login_required
def history(request):
    today = timezone.localdate()
    entries = DailyCheckin.objects.filter(user=request.user, date__lte=today)[:60]
    return render(request, "tracking/history.html", {"entries": entries, "today": today})


@login_required
@require_POST
def checkin_delete(request, pk):
    entry = get_object_or_404(DailyCheckin, pk=pk, user=request.user)
    if entry.date == timezone.localdate():
        messages.error(request, "Không thể xóa check-in hôm nay để tạo lại lần nữa.")
        return redirect("history")
    entry.delete()
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
