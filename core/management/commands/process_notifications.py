from django.core.management.base import BaseCommand

from core.services.notifications import process_due_notifications


class Command(BaseCommand):
    help = "Отправляет уведомления ExamSL, время которых наступило. Запускайте каждую минуту."

    def handle(self, *args, **options):
        stats = process_due_notifications()
        self.stdout.write(self.style.SUCCESS(f"Готово: {stats}"))
