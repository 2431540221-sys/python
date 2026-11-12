from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from accounts.apiutils import api, form_errors, read_json

from .forms import CheckinForm, JournalForm
from .models import DailyCheckin, JournalEntry


def checkin_json(c):
    return {
        "id": c.pk, "date": c.date.isoformat(), "mood": c.mood, "sleep_hours": c.sleep_hours,
        "activity_type": c.activity_type, "activity_minutes": c.activity_minutes, "note": c.note,
    }


def journal_json(j):
    return {
        "id": j.pk, "title": j.title, "content": j.content, "tags": j.tag_list,
        "created_at": j.created_at.isoformat(), "updated_at": j.updated_at.isoformat(),
    }


@api(methods=("GET", "POST"))
def checkin_list(request):
    if request.method == "GET":
        qs = DailyCheckin.objects.filter(user=request.user)[:90]
        return JsonResponse({"checkins": [checkin_json(c) for c in qs]})
    data = read_json(request)
    try:
        existing = DailyCheckin.objects.filter(user=request.user, date=data["date"]).first() if data.get("date") else None
    except (ValidationError, ValueError):
        existing = None      # ngày sai định dạng: để form báo lỗi
    form = CheckinForm(data, instance=existing)
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    entry = form.save(commit=False)
    entry.user = request.user
    entry.save()
    return JsonResponse(checkin_json(entry), status=200 if existing else 201)


@api(methods=("GET", "POST"))
def journal_list(request):
    if request.method == "GET":
        return JsonResponse({"journals": [journal_json(j) for j in JournalEntry.objects.filter(user=request.user)]})
    form = JournalForm(read_json(request))
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    entry = form.save(commit=False)
    entry.user = request.user
    entry.save()
    return JsonResponse(journal_json(entry), status=201)


@api(methods=("GET", "PUT", "DELETE"))
def journal_detail(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, user=request.user)    # journal người khác -> 404
    if request.method == "GET":
        return JsonResponse(journal_json(entry))
    if request.method == "DELETE":
        entry.delete()
        return JsonResponse({"deleted": True})
    data = {"title": entry.title, "content": entry.content, "tags": entry.tags, **read_json(request)}
    form = JournalForm(data, instance=entry)
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    return JsonResponse(journal_json(form.save()))
