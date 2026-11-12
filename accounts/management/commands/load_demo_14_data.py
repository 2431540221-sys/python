from django.core.management.base import BaseCommand
from accounts.demo import create_demo_accounts

class Command(BaseCommand):
    help = "Tạo dữ liệu demo 14 ngày (không cần truyền --days)."

    def handle(self, *args, **options):
        days = 14
        for username, password in create_demo_accounts(days):
            self.stdout.write(self.style.SUCCESS(f"  {username} / {password}"))
        self.stdout.write("✅ Đã nạp dữ liệu demo 14 ngày. Hãy chạy server và truy cập /history/.")
