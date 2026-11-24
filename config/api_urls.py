"""Toàn bộ REST API (JSON), xác thực bằng JWT: Authorization: Bearer <access_token>."""
from django.urls import path

from accounts import api as accounts_api
from coach import api as coach_api
from habits import api as habits_api
from insights import api as insights_api
from tracking import api as tracking_api

urlpatterns = [
    # Task 1: đăng ký / đăng nhập JWT, dữ liệu cá nhân, thống kê ẩn danh cho admin
    path("auth/register/", accounts_api.register, name="api_register"),
    path("auth/login/", accounts_api.login, name="api_login"),
    path("auth/refresh/", accounts_api.refresh, name="api_refresh"),
    path("me/", accounts_api.me, name="api_me"),
    path("me/data/", accounts_api.delete_my_data, name="api_delete_data"),
    path("admin/stats/", accounts_api.admin_stats, name="api_admin_stats"),
    # Task 2: thói quen & streak
    path("habits/", habits_api.habit_list, name="api_habits"),
    path("habits/<int:pk>/", habits_api.habit_detail, name="api_habit_detail"),
    path("habits/<int:pk>/check/", habits_api.habit_check, name="api_habit_check"),
    # Task 3: check-in & journal
    path("checkins/", tracking_api.checkin_list, name="api_checkins"),
    path("journals/", tracking_api.journal_list, name="api_journals"),
    path("journals/<int:pk>/", tracking_api.journal_detail, name="api_journal_detail"),
    # Task 4: tổng hợp theo tuần/tháng, thông báo
    path("stats/", insights_api.stats, name="api_stats"),
    path("notifications/", insights_api.notifications, name="api_notifications"),
    # Task 5: AI coach
    path("coach/weekly/", coach_api.weekly, name="api_coach_weekly"),
]
