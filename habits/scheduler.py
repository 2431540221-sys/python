"""
Job chạy nền theo giờ (APScheduler): mỗi phút gọi
  - send_due_reminders()                    (Task 2: nhắc nhở theo giờ)
  - create_streak_risk_notifications()      (Task 4: báo sắp mất streak)

Scheduler tự bật khi chạy `runserver` hoặc `gunicorn`. Khi deploy nhiều worker thì mỗi worker có
một scheduler, nhưng job idempotent nên không tạo thông báo trùng. Tắt bằng ENABLE_SCHEDULER=0
rồi dùng cron gọi `python manage.py send_reminders`.
"""
import logging
import os
import sys

from django.conf import settings

logger = logging.getLogger(__name__)
_started = False


def run_all_jobs():
    from insights.services import create_streak_risk_notifications

    from .services import send_due_reminders

    try:
        reminders = send_due_reminders()
        risks = create_streak_risk_notifications()
        if reminders or risks:
            logger.info("Scheduler: %s nhắc nhở, %s cảnh báo sắp mất chuỗi", reminders, risks)
    except Exception:   # job nền không được làm sập server
        logger.exception("Scheduler job lỗi")


def _is_server_process():
    argv = " ".join(sys.argv)
    if "runserver" in argv:
        # runserver có autoreloader: chỉ bật ở tiến trình con thực sự phục vụ request
        return os.environ.get("RUN_MAIN") == "true" or "--noreload" in argv
    return "gunicorn" in argv or os.environ.get("FORCE_SCHEDULER") == "1"


def start_scheduler_if_needed():
    global _started
    if _started or not settings.ENABLE_SCHEDULER or not _is_server_process():
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_job(run_all_jobs, "interval", seconds=60, id="wellbeing_jobs",
                      max_instances=1, coalesce=True, replace_existing=True)
    scheduler.start()
    _started = True
    logger.info("Đã bật scheduler nhắc nhở (mỗi 60 giây).")
