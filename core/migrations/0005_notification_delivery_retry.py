from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_exam_google_sheets_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationlog",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="notificationlog",
            name="next_retry_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="notificationlog",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Ожидает отправки"),
                    ("sent", "Отправлено"),
                    ("failed", "Ошибка"),
                    ("skipped", "Пропущено"),
                ],
                max_length=20,
            ),
        ),
    ]
