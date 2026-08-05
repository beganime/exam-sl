import time

from django.core.management.base import BaseCommand

from core.services.notifications import process_due_notifications


class Command(BaseCommand):
    help = "Постоянный worker уведомлений для локального запуска/простого VPS."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30)

    def handle(self, *args, **options):
        interval = max(options["interval"], 10)
        self.stdout.write(f"Worker запущен, интервал {interval} сек. Остановка: Ctrl+C")
        while True:
            try:
                stats = process_due_notifications()
                if any(stats.values()):
                    self.stdout.write(f"Обработано: {stats}")
            except Exception as exc:
                self.stderr.write(f"Ошибка worker: {exc}")
            time.sleep(interval)
