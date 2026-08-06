import time

from django.conf import settings
from django.core.management.base import BaseCommand

from core.services.google_sheets import sync_exams


class Command(BaseCommand):
    help = "Синхронизирует экзамены из основной Google Sheets книги."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=int, default=settings.GOOGLE_SHEETS_POLL_SECONDS)

    def handle(self, *args, **options):
        while True:
            self.stdout.write(str(sync_exams()))
            if not options["watch"]:
                return
            time.sleep(max(options["interval"], 15))
