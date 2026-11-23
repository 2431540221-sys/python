import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyWellbeingIndex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(default=django.utils.timezone.localdate)),
                ("score", models.FloatField(blank=True, null=True)),
                ("mood_score", models.FloatField(blank=True, null=True)),
                ("sleep_score", models.FloatField(blank=True, null=True)),
                ("activity_score", models.FloatField(blank=True, null=True)),
                ("habit_score", models.FloatField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wellbeing_indices", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-date"],
                "constraints": [models.UniqueConstraint(fields=("user", "date"), name="one_wellbeing_index_per_day")],
            },
        ),
    ]
