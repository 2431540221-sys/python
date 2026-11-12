from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import HabitForm
from .models import Habit
from .services import habits_with_stats, get_habit_stats, recent_days, toggle_day


def _own_habit(request, pk):
    # Luôn lọc theo user: habit của người khác trả về 404 (không tiết lộ là có tồn tại)
    return get_object_or_404(Habit, pk=pk, user=request.user)


@login_required
def habit_list(request):
    return render(request, "habits/list.html", {"habits": habits_with_stats(request.user)})


@login_required
def habit_create(request):
    form = HabitForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        habit = form.save(commit=False)
        habit.user = request.user
        habit.save()
        messages.success(request, f"Đã thêm thói quen “{habit.name}”.")
        return redirect("habit_detail", pk=habit.pk)
    return render(request, "habits/form.html", {"form": form, "title": "Thêm thói quen"})


@login_required
def habit_detail(request, pk):
    habit = _own_habit(request, pk)
    stats = get_habit_stats(habit)
    return render(request, "habits/detail.html", {
        "habit": habit,
        "stats": stats,
        "calendar": recent_days(habit, 35),
    })


@login_required
def habit_update(request, pk):
    habit = _own_habit(request, pk)
    form = HabitForm(request.POST or None, instance=habit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật thói quen.")
        return redirect("habit_detail", pk=habit.pk)
    return render(request, "habits/form.html", {"form": form, "title": "Sửa thói quen", "habit": habit})


@login_required
def habit_delete(request, pk):
    habit = _own_habit(request, pk)
    if request.method == "POST":
        habit.delete()
        messages.success(request, "Đã xóa thói quen và lịch sử của nó.")
        return redirect("habit_list")
    return render(request, "habits/confirm_delete.html", {"habit": habit})


@login_required
@require_POST
def habit_toggle(request, pk):
    habit = _own_habit(request, pk)
    raw = request.POST.get("date")
    try:
        day = date.fromisoformat(raw) if raw else timezone.localdate()
        done = toggle_day(habit, day)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        if done:
            stats = get_habit_stats(habit)
            messages.success(request, f"Đã hoàn thành “{habit.name}”. Chuỗi hiện tại: {stats['current_streak']} ngày.")
        else:
            messages.info(request, f"Đã bỏ đánh dấu “{habit.name}”.")
    nxt = request.POST.get("next")
    return redirect("habit_detail", pk=pk) if nxt == "detail" else redirect("habit_list")
