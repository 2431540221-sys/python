import time

from django.core.management.base import BaseCommand

from habits.scheduler import run_all_jobs
from habits.services import send_due_reminders
from insights.services import create_streak_risk_notifications, create_wellbeing_trend_notifications


class Command(BaseCommand):
    help = "Tạo nhắc nhở đến giờ và cảnh báo sắp mất chuỗi (dùng cho cron khi không bật scheduler)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Chạy lặp mỗi 60 giây (để thử ở máy local).")

    def handle(self, *args, **options):
        if not options["loop"]:
            reminders = send_due_reminders()
            risks = create_streak_risk_notifications()
            wellbeing = create_wellbeing_trend_notifications()
            self.stdout.write(self.style.SUCCESS(
                f"Đã tạo {reminders} nhắc nhở, {risks} cảnh báo sắp mất chuỗi và "
                f"{wellbeing} lời nhắc wellbeing hỗ trợ."
            ))
            return
        self.stdout.write("Đang chạy lặp mỗi 60 giây. Nhấn Ctrl+C để dừng.")
        try:
            while True:
                run_all_jobs()
                time.sleep(60)
        except KeyboardInterrupt:
            self.stdout.write("Đã dừng.")
