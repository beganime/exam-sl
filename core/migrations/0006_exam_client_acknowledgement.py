from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0005_notification_delivery_retry')]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='external_exam_id',
            field=models.CharField(blank=True, max_length=80, verbose_name='ID экзамена в Students Life'),
        ),
        migrations.AddField(
            model_name='exam',
            name='client_acknowledged_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Клиент ознакомился'),
        ),
    ]
