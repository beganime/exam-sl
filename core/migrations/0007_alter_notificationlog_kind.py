from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0006_exam_client_acknowledgement')]

    operations = [
        migrations.AlterField(
            model_name='notificationlog',
            name='kind',
            field=models.CharField(
                choices=[
                    ('day_before_08', 'За день, 08:00'),
                    ('day_before_20', 'За день, 20:00'),
                    ('before_30_minutes', 'За 30 минут'),
                    ('custom', 'Дополнительное'),
                    ('test', 'Тестовое'),
                    ('sheet_new', 'Новый экзамен из Google Sheets'),
                    ('sheet_updated', 'Изменение экзамена в Google Sheets'),
                    ('client_seen', 'Клиент ознакомился'),
                ],
                max_length=30,
            ),
        ),
    ]
