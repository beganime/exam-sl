from datetime import timedelta
from unittest.mock import Mock
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import BrowserDevice, Exam, NotificationLog
from core.services.google_sheets import notify_change, retry_failed_change_notifications, sync_exams


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

    @override_settings(
        SHEET_NOTIFICATION_MAX_ATTEMPTS=3,
        SHEET_NOTIFICATION_RETRY_BASE_SECONDS=30,
    )
    @patch("core.services.google_sheets.StudentsLifeClient.resolve_user_ids", return_value=[])
    @patch("core.services.google_sheets.send_push")
    def test_failed_change_notification_is_retried_without_losing_exam(self, send_mock, _tokens_mock):
        manager = User.objects.create_user(username="retry-manager")
        BrowserDevice.objects.create(user=manager, token="manager-token")
        exam = Exam.objects.create(
            source_id="EXAM-RETRY",
            client_full_name="Иван Иванов",
            exam_at=timezone.now() + timedelta(days=2),
            university="КФУ",
            subject="Русский язык",
            created_by=manager,
        )
        send_mock.side_effect = RuntimeError("Firebase temporarily unavailable")

        first = notify_change(exam, created=True)

        log = NotificationLog.objects.get(exam=exam, kind=NotificationLog.Kind.SHEET_NEW)
        self.assertEqual(first["status"], NotificationLog.Status.FAILED)
        self.assertEqual(log.attempt_count, 1)
        self.assertIsNotNone(log.next_retry_at)

        send_mock.side_effect = None
        send_mock.return_value = {
            "success_count": 1,
            "failure_count": 0,
            "invalid_tokens": [],
            "errors": [],
        }
        retried = retry_failed_change_notifications(now=log.next_retry_at + timedelta(seconds=1))

        log.refresh_from_db()
        self.assertEqual(retried, {"sent": 1, "failed": 0})
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.attempt_count, 2)
        self.assertIsNone(log.next_retry_at)

    @override_settings(FIREBASE_CREDENTIALS="missing-firebase.json", FIREBASE_LEGACY_CREDENTIALS="")
    @patch("core.services.google_sheets.StudentsLifeClient.find_tokens_for_client", return_value=([], []))
    @patch("core.services.google_sheets.StudentsLifeClient.upsert_client_exam", return_value={"sync_status": "created"})
    @patch("core.services.google_sheets.StudentsLifeClient.resolve_user_ids", return_value=["77"])
    @patch("core.services.google_sheets.send_push")
    def test_in_app_exam_delivery_succeeds_without_firebase(
        self, send_mock, _resolve_mock, upsert_mock, _tokens_mock
    ):
        manager = User.objects.create_user(username="in-app-manager")
        exam = Exam.objects.create(
            source_id="EXAM-IN-APP",
            sl_id="SL-001",
            client_full_name="Иван Иванов",
            exam_at=timezone.now() + timedelta(days=2),
            university="КФУ",
            subject="Русский язык",
            created_by=manager,
        )

        result = notify_change(exam, created=True)

        self.assertEqual(result["status"], NotificationLog.Status.SENT)
        self.assertEqual(result["success_count"], 1)
        upsert_mock.assert_called_once()
        send_mock.assert_not_called()
