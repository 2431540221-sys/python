import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Tạo cặp khóa VAPID để cấu hình Web Push."

    def handle(self, *args, **options):
        private_key = ec.generate_private_key(ec.SECP256R1())
        private_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        self.stdout.write("VAPID_PRIVATE_KEY=" + base64.b64encode(private_der).decode("ascii"))
        self.stdout.write(
            "VAPID_PUBLIC_KEY="
            + base64.urlsafe_b64encode(public_bytes).decode("ascii").rstrip("=")
        )
