from django.core.management.base import BaseCommand

from accounts.demo import create_demo_accounts


class Command(BaseCommand):
    help = "Tạo tài khoản demo (usera, userb, userc, admin) cùng dữ liệu 30 ngày."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        for username, password in create_demo_accounts(options["days"]):
            self.stdout.write(self.style.SUCCESS(f"  {username} / {password}"))
        self.stdout.write("Đã nạp dữ liệu demo. Hãy ĐỔI hoặc XÓA các tài khoản này khi dùng thật.")
