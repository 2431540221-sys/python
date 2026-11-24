from datetime import date

from django.db import IntegrityError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

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
        qs = DailyCheckin.objects.filter(user=request.user, date__lte=timezone.localdate())[:90]
        return JsonResponse({"checkins": [checkin_json(c) for c in qs]})
    data = read_json(request)
    try:
        day = date.fromisoformat(data["date"]) if data.get("date") else timezone.localdate()
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_date", "detail": "Ngày check-in không hợp lệ."}, status=400)
    if day != timezone.localdate():
        return JsonResponse(
            {"error": "invalid_date", "detail": "Chỉ được check-in cho ngày hôm nay."},
            status=400,
        )
    if DailyCheckin.objects.filter(user=request.user, date=day).exists():
        return JsonResponse(
            {"error": "already_checked_in", "detail": "Bạn đã check-in hôm nay rồi."},
            status=409,
        )
    form = CheckinForm(data)
    if not form.is_valid():
        return JsonResponse({"error": "validation_error", "fields": form_errors(form)}, status=400)
    entry = form.save(commit=False)
    entry.user = request.user
    entry.date = day
    try:
        with transaction.atomic():
            entry.save()
    except IntegrityError:
        return JsonResponse(
            {"error": "already_checked_in", "detail": "Bạn đã check-in hôm nay rồi."},
            status=409,
        )
    return JsonResponse(checkin_json(entry), status=201)


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
