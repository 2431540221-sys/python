from datetime import date

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from accounts.apiutils import ApiError, api, form_errors, read_json

from .forms import HabitForm
from .models import Habit
from .services import get_habit_stats, toggle_day


def habit_json(habit):
    return {
        "id": habit.pk, "name": habit.name, "description": habit.description,
        "weekly_target": habit.weekly_target, "streak_goal": habit.streak_goal,
        "reminder_enabled": habit.reminder_enabled,
        "reminder_time": habit.reminder_time.strftime("%H:%M") if habit.reminder_time else None,
        "is_active": habit.is_active,
        "stats": get_habit_stats(habit),
    }


def _form_data(data, habit=None):
    base = {}
    if habit is not None:
        base = {
            "name": habit.name, "description": habit.description, "weekly_target": habit.weekly_target,
            "streak_goal": habit.streak_goal or "", "reminder_enabled": habit.reminder_enabled,
            "reminder_time": habit.reminder_time.strftime("%H:%M") if habit.reminder_time else "",
        }
    base.update({k: v for k, v in data.items() if k in HabitForm.Meta.fields})
    return base


@api(methods=("GET", "POST"))
def habit_list(request):
    if request.method == "GET":
        habits = Habit.objects.filter(user=request.user)     # chỉ habit của chính mình
        return JsonResponse({"habits": [habit_json(h) for h in habits]})
    form = HabitForm(_form_data(read_json(request)))
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    habit = form.save(commit=False)
    habit.user = request.user
    habit.save()
    return JsonResponse(habit_json(habit), status=201)


@api(methods=("GET", "PUT", "DELETE"))
def habit_detail(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)   # người khác -> 404
    if request.method == "GET":
        return JsonResponse(habit_json(habit))
    if request.method == "DELETE":
        habit.delete()
        return JsonResponse({"deleted": True})
    form = HabitForm(_form_data(read_json(request), habit), instance=habit)
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    return JsonResponse(habit_json(form.save()))


@api(methods=("POST",))
def habit_check(request, pk):
    """Đánh dấu hoàn thành (hoặc bỏ đánh dấu) một ngày. Body: {"date": "YYYY-MM-DD"} (mặc định hôm nay)."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    raw = read_json(request).get("date")
    try:
        day = date.fromisoformat(raw) if raw else None
        done = toggle_day(habit, day)
    except ValueError as exc:
        raise ApiError(400, "invalid_date", str(exc))
    return JsonResponse({"done": done, "habit": habit_json(habit)})
