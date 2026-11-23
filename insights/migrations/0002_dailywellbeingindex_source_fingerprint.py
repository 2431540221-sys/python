from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("insights", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailywellbeingindex",
            name="source_fingerprint",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
