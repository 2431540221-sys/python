import json
from contextlib import asynccontextmanager
from datetime import date

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response

from accounts import security
from accounts.forms import RegisterForm
from accounts.services import admin_statistics, delete_user_data
from accounts.tokens import create_access_token, create_refresh_token, user_from_token
from coach import safety
from coach.models import CoachReport
from coach.service import ConsentRequired, generate_report
from coach_service.main import router as internal_ai_router
from dbsync.api import router as database_sync_router
from dbsync.worker import start_worker_if_configured
from habits.forms import HabitForm
from habits.models import Habit, Notification
from habits.services import get_habit_stats, mark_day_done
from insights.services import PERIODS, create_streak_risk_notifications, period_stats
from tracking.forms import CheckinForm, JournalForm
from tracking.models import DailyCheckin, JournalEntry

router = APIRouter(prefix="/api")


@asynccontextmanager
async def lifespan(_app):
    start_worker_if_configured()
    yield


api_app = FastAPI(title="Mầm API", version="1.0.0", lifespan=lifespan)


class ApiError(Exception):
    def __init__(self, status, code, detail=""):
        self.status = status
        self.code = code
        self.detail = detail


@api_app.exception_handler(ApiError)
async def handle_api_error(request, exc):
    return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=exc.status)


@api_app.exception_handler(Http404)
async def handle_not_found(request, exc):
    return JSONResponse({"detail": "Not found"}, status_code=404)


@api_app.exception_handler(ValidationError)
async def handle_validation_error(request, exc):
    return JSONResponse({"detail": "Invalid request"}, status_code=400)


@router.get("")
def api_root():
    return Response(status_code=307, headers={"Location": "/api/"})


async def read_json(request: Request):
    body = await request.body()
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "invalid_json", "Nội dung gửi lên không phải JSON hợp lệ.")
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "JSON phải là một object.")
    return data


def current_user(request: Request):
    authorization = request.headers.get("authorization", "")
    if authorization[:7].lower() == "bearer ":
        token = authorization[7:].strip()
    elif request.method in {"GET", "HEAD", "OPTIONS"}:
        token = request.cookies.get(settings.JWT_COOKIE_NAME)
    else:
        token = None
    user = user_from_token(token) if token else None
    if user is None:
        raise ApiError(401, "unauthorized", "Cần đăng nhập hoặc gửi Bearer token hợp lệ.")
    return user


def admin_user(user=Depends(current_user)):
    if user.role != "admin":
        raise ApiError(403, "forbidden", "Vai trò của bạn không được phép.")
    return user


def form_errors(form):
    return {field: [str(error) for error in errors] for field, errors in form.errors.items()}


def user_json(user):
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "consent_ai": user.consent_ai,
    }


def token_pair(user):
    return {
        "access": create_access_token(user),
        "refresh": create_refresh_token(user),
        "token_type": "Bearer",
    }


@router.post("/auth/register/", status_code=201)
def register(data=Depends(read_json)):
    password = data.get("password", "")
    form = RegisterForm({
        "username": data.get("username", ""),
        "email": data.get("email", ""),
        "password1": password,
        "password2": password,
        "consent_ai": bool(data.get("consent_ai", False)),
    })
    if not form.is_valid():
        return JSONResponse(
            {"error": "validation_error", "fields": form_errors(form)}, status_code=400
        )
    user = form.save()
    return {"user": user_json(user), **token_pair(user)}


@router.post("/auth/login/")
def login(request: Request, data=Depends(read_json)):
    username, password = data.get("username", ""), data.get("password", "")
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",", 1)[0].strip() if forwarded else (
        request.client.host if request.client else ""
    )
    if security.is_locked(username, ip):
        raise ApiError(429, "too_many_attempts", "Sai quá nhiều lần, thử lại sau 15 phút.")
    user = authenticate(None, username=username, password=password)
    if user is None:
        security.register_failure(username, ip)
        raise ApiError(401, "invalid_credentials", "Sai tên đăng nhập hoặc mật khẩu.")
    security.clear_failures(username, ip)
    return {"user": user_json(user), **token_pair(user)}


@router.post("/auth/refresh/")
def refresh(data=Depends(read_json)):
    user = user_from_token(data.get("refresh", ""), expected_type="refresh")
    if user is None:
        raise ApiError(401, "invalid_token", "Refresh token không hợp lệ hoặc đã hết hạn.")
    return {"access": create_access_token(user), "token_type": "Bearer"}


@router.get("/me/")
def me_get(user=Depends(current_user)):
    return user_json(user)


@router.delete("/me/")
def me_delete(data=Depends(read_json), user=Depends(current_user)):
    if not authenticate(None, username=user.username, password=data.get("password", "")):
        raise ApiError(403, "wrong_password", "Cần gửi đúng mật khẩu để xóa tài khoản.")
    user.delete()
    return {"deleted": True, "detail": "Tài khoản và toàn bộ dữ liệu đã bị xóa."}


@router.delete("/me/data/")
def delete_me_data(user=Depends(current_user)):
    return {"deleted": delete_user_data(user)}


@router.get("/admin/stats/")
def admin_stats(user=Depends(admin_user)):
    return admin_statistics()


def habit_json(habit):
    return {
        "id": habit.pk,
        "name": habit.name,
        "description": habit.description,
        "weekly_target": habit.weekly_target,
        "streak_goal": habit.streak_goal,
        "reminder_enabled": habit.reminder_enabled,
        "reminder_time": habit.reminder_time.strftime("%H:%M") if habit.reminder_time else None,
        "is_active": habit.is_active,
        "stats": get_habit_stats(habit),
    }


def habit_form_data(data, habit=None):
    values = {}
    if habit is not None:
        values = {
            "name": habit.name,
            "description": habit.description,
            "weekly_target": habit.weekly_target,
            "streak_goal": habit.streak_goal or "",
            "reminder_enabled": habit.reminder_enabled,
            "reminder_time": habit.reminder_time.strftime("%H:%M") if habit.reminder_time else "",
        }
    values.update({key: value for key, value in data.items() if key in HabitForm.Meta.fields})
    return values


@router.get("/habits/")
def habit_list(user=Depends(current_user)):
    return {"habits": [habit_json(habit) for habit in Habit.objects.filter(user=user)]}


@router.post("/habits/", status_code=201)
def habit_create(data=Depends(read_json), user=Depends(current_user)):
    form = HabitForm(habit_form_data(data))
    if not form.is_valid():
        return JSONResponse(
            {"error": "validation_error", "fields": form_errors(form)}, status_code=400
        )
    habit = form.save(commit=False)
    habit.user = user
    habit.save()
    return habit_json(habit)


@router.get("/habits/{pk}/")
def habit_get(pk: int, user=Depends(current_user)):
    habit = get_object_or_404(Habit, pk=pk, user=user)
    return habit_json(habit)


@router.put("/habits/{pk}/")
def habit_update(pk: int, data=Depends(read_json), user=Depends(current_user)):
    habit = get_object_or_404(Habit, pk=pk, user=user)
    form = HabitForm(habit_form_data(data, habit), instance=habit)
    if not form.is_valid():
        return JSONResponse(
            {"error": "validation_error", "fields": form_errors(form)}, status_code=400
        )
    return habit_json(form.save())


@router.delete("/habits/{pk}/")
def habit_delete(pk: int, user=Depends(current_user)):
    habit = get_object_or_404(Habit, pk=pk, user=user)
    habit.delete()
    return {"deleted": True}


@router.post("/habits/{pk}/check/")
def habit_check(pk: int, data=Depends(read_json), user=Depends(current_user)):
    habit = get_object_or_404(Habit, pk=pk, user=user)
    raw_day = data.get("date")
    try:
        day = date.fromisoformat(raw_day) if raw_day else None
        mark_day_done(habit, day)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "invalid_date", str(exc))
    return {"done": True, "habit": habit_json(habit)}


def checkin_json(checkin):
    return {
        "id": checkin.pk,
        "date": checkin.date.isoformat(),
        "mood": checkin.mood,
        "sleep_hours": checkin.sleep_hours,
        "activity_type": checkin.activity_type,
        "activity_minutes": checkin.activity_minutes,
        "note": checkin.note,
    }


def journal_json(journal):
    return {
        "id": journal.pk,
        "title": journal.title,
        "content": journal.content,
        "tags": journal.tag_list,
        "created_at": journal.created_at.isoformat(),
        "updated_at": journal.updated_at.isoformat(),
    }


@router.get("/checkins/")
def checkin_list(user=Depends(current_user)):
    checkins = DailyCheckin.objects.filter(user=user, date__lte=timezone.localdate())[:90]
    return {"checkins": [checkin_json(checkin) for checkin in checkins]}


@router.post("/checkins/")
def checkin_create(data=Depends(read_json), user=Depends(current_user)):
    try:
        day = date.fromisoformat(data["date"]) if data.get("date") else timezone.localdate()
    except (TypeError, ValueError):
        raise ApiError(400, "invalid_date", "Ngày check-in không hợp lệ.")
    if day != timezone.localdate():
        raise ApiError(400, "invalid_date", "Chỉ được check-in cho ngày hôm nay.")
    if DailyCheckin.objects.filter(user=user, date=day).exists():
        raise ApiError(409, "already_checked_in", "Bạn đã check-in hôm nay rồi.")
    form = CheckinForm(data)
    if not form.is_valid():
        return JSONResponse(
            {"error": "validation_error", "fields": form_errors(form)}, status_code=400
        )
    checkin = form.save(commit=False)
    checkin.user = user
    checkin.date = day
    try:
        with transaction.atomic():
            checkin.save()
    except IntegrityError:
        raise ApiError(409, "already_checked_in", "Bạn đã check-in hôm nay rồi.")
    return JSONResponse(checkin_json(checkin), status_code=201)


@router.get("/journals/")
def journal_list(user=Depends(current_user)):
    journals = JournalEntry.objects.filter(user=user)
    return {"journals": [journal_json(journal) for journal in journals]}


@router.post("/journals/", status_code=201)
def journal_create(data=Depends(read_json), user=Depends(current_user)):
    form = JournalForm(data)
    if not form.is_valid():
        return JSONResponse(
            {"error": "validation_error", "fields": form_errors(form)}, status_code=400
        )
    journal = form.save(commit=False)
    journal.user = user
    journal.save()
    return journal_json(journal)


@router.get("/journals/{pk}/")
def journal_get(pk: int, user=Depends(current_user)):
    journal = get_object_or_404(JournalEntry, pk=pk, user=user)
    return journal_json(journal)


@router.put("/journals/{pk}/")
def journal_update(pk: int, data=Depends(read_json), user=Depends(current_user)):
    journal = get_object_or_404(JournalEntry, pk=pk, user=user)
    values = {"title": journal.title, "content": journal.content, "tags": journal.tags, **data}
    form = JournalForm(values, instance=journal)
    if not form.is_valid():
        return JSONResponse(
            {"error": "validation_error", "fields": form_errors(form)}, status_code=400
        )
    return journal_json(form.save())


@router.delete("/journals/{pk}/")
def journal_delete(pk: int, user=Depends(current_user)):
    journal = get_object_or_404(JournalEntry, pk=pk, user=user)
    journal.delete()
    return {"deleted": True}


@router.get("/stats/")
def stats(period: str = "week", user=Depends(current_user)):
    if period not in PERIODS:
        raise ApiError(400, "invalid_period", "period phải là week hoặc month.")
    return period_stats(user, period)


@router.get("/notifications/")
def notifications(user=Depends(current_user)):
    create_streak_risk_notifications(user=user)
    items = Notification.objects.filter(user=user)[:50]
    return {
        "unread": Notification.objects.filter(user=user, is_read=False).count(),
        "notifications": [
            {
                "id": item.pk,
                "kind": item.kind,
                "title": item.title,
                "body": item.body,
                "is_read": item.is_read,
                "created_at": timezone.localtime(item.created_at).isoformat(),
            }
            for item in items
        ],
    }


def report_json(report):
    return {
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "summary": report.summary,
        "patterns": report.patterns,
        "goals": report.goals,
        "actions": report.actions,
        "source": report.source,
        "disclaimer": safety.DISCLAIMER,
    }


@router.get("/coach/weekly/")
def coach_weekly_get(user=Depends(current_user)):
    report = CoachReport.objects.filter(user=user).first()
    if report is None:
        raise ApiError(404, "no_report", "Chưa có bản tóm tắt nào. Hãy gọi POST để tạo.")
    return report_json(report)


@router.post("/coach/weekly/", status_code=201)
def coach_weekly_create(user=Depends(current_user)):
    try:
        report = generate_report(user)
    except ConsentRequired:
        raise ApiError(
            403, "consent_required",
            "Bạn chưa bật quyền AI Coach trong phần Tài khoản.",
        )
    return report_json(report)


api_app.include_router(router)
api_app.include_router(database_sync_router)
api_app.include_router(internal_ai_router, prefix="/internal-ai")
