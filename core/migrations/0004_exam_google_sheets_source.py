from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0003_exam_responsible_manager")]

    operations = [
        migrations.AddField(model_name="exam", name="client_email", field=models.EmailField(blank=True, max_length=254, verbose_name="Почта")),
        migrations.AddField(model_name="exam", name="program", field=models.CharField(blank=True, max_length=255, verbose_name="Направление")),
        migrations.AddField(model_name="exam", name="sl_id", field=models.CharField(blank=True, db_index=True, max_length=32, verbose_name="SL-ID")),
        migrations.AddField(model_name="exam", name="source_id", field=models.CharField(blank=True, max_length=120, null=True, unique=True, verbose_name="ID строки источника")),
        migrations.AddField(model_name="exam", name="source_notification_version", field=models.PositiveIntegerField(default=0, verbose_name="Версия уведомления")),
        migrations.AddField(model_name="exam", name="source_row", field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Строка Google Sheets")),
        migrations.AddField(model_name="exam", name="source_synced_at", field=models.DateTimeField(blank=True, null=True, verbose_name="Синхронизировано")),
        migrations.AlterField(
            model_name="notificationlog",
            name="kind",
            field=models.CharField(
                choices=[
                    ("day_before_08", "За день, 08:00"),
                    ("day_before_20", "За день, 20:00"),
                    ("before_30_minutes", "За 30 минут"),
                    ("custom", "Дополнительное"),
                    ("test", "Тестовое"),
                    ("sheet_new", "Новый экзамен из Google Sheets"),
                    ("sheet_updated", "Изменение экзамена в Google Sheets"),
                ],
                max_length=30,
            ),
        ),
    ]
