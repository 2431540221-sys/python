from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_notifications_enabled",
            field=models.BooleanField(default=False, verbose_name="Nhận thông báo qua email"),
        ),
    ]
