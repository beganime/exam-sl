from unittest.mock import Mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Exam
from core.services.google_sheets import sync_exams


class FakeSource:
    def __init__(self):
        self.exam_at = "10.08.2026 12:30"

    def rows(self, sheet_name):
        if sheet_name == "Общее":
            return [{"Айди": "SL-001", "ФИО абитуриента": "Иван Иванов"}]
        return [{
            "ID экзамена": "EXAM-001",
            "Айди": "SL-001",
            "Вуз": "КФУ",
            "Направление": "Лечебное дело",
            "Экзамен": "Русский язык",
            "Дата и время": self.exam_at,
            "логин": "ivan",
            "Пароль": "Ivan_0710",
            "почта": "ivan@example.com",
            "Место или ссылка": "https://example.com/exam",
            "Ответственный": "",
            "Версия уведомления": "1",
        }]


@override_settings(GOOGLE_SHEETS_GENERAL_SHEET="Общее", GOOGLE_SHEETS_EXAMS_SHEET="Экзамены")
class GoogleSheetsSyncTests(TestCase):
    def test_new_row_notifies_once_and_date_change_notifies_again(self):
        source = FakeSource()
        notifier = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            first = sync_exams(source=source, notifier=notifier)
        with self.captureOnCommitCallbacks(execute=True):
            second = sync_exams(source=source, notifier=notifier)
        source.exam_at = "10.08.2026 13:00"
        with self.captureOnCommitCallbacks(execute=True):
            changed = sync_exams(source=source, notifier=notifier)

        exam = Exam.objects.get(source_id="EXAM-001")
        self.assertEqual(exam.sl_id, "SL-001")
        self.assertEqual(exam.client_full_name, "Иван Иванов")
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(changed["changed"], 1)
        self.assertEqual(notifier.call_count, 2)

    def test_health_is_public(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @override_settings(MANAGER_REGISTRATION_ENABLED=False)
    def test_manager_registration_is_disabled(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 403)
