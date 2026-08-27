from django.core.management.base import BaseCommand

from core.services.google_sheets import GoogleSheetsSource


class Command(BaseCommand):
    help = "Create and format the simplified ExamSL Google Sheets tab."

    def handle(self, *args, **options):
        result = GoogleSheetsSource().prepare_exam_sheet()
        self.stdout.write(self.style.SUCCESS(f"Prepared {result['sheet']} ({result['client_column']})."))
