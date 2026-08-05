from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import BrowserDevice, Exam, NotificationLog
from core.services.notifications import process_due_notifications


class NotificationWorkerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("manager")
        BrowserDevice.objects.create(user=self.user, token="token-1", device_id="test")
        self.exam = Exam.objects.create(
            client_full_name="Тест Клиент",
            exam_at=timezone.make_aware(datetime(2026, 7, 16, 11, 0)),
            university="ТГУ",
            subject="Тест",
            created_by=self.user,
        )

    @patch("core.services.notifications.send_push")
    def test_worker_sends_due_morning_notification_once(self, send_mock):
        send_mock.return_value = {"success_count": 1, "failure_count": 0, "invalid_tokens": [], "errors": []}
        now = timezone.make_aware(datetime(2026, 7, 15, 8, 1))
        first = process_due_notifications(now=now)
        second = process_due_notifications(now=now)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(NotificationLog.objects.count(), 1)
        send_mock.assert_called_once()

    @patch("core.services.notifications.send_push")
    def test_custom_notification_can_be_earlier_than_two_days(self, send_mock):
        send_mock.return_value = {"success_count": 1, "failure_count": 0, "invalid_tokens": [], "errors": []}
        now = timezone.make_aware(datetime(2026, 7, 10, 12, 1))
        self.exam.exam_at = timezone.make_aware(datetime(2026, 7, 20, 11, 0))
        self.exam.custom_notify_at = timezone.make_aware(datetime(2026, 7, 10, 12, 0))
        self.exam.save()
        result = process_due_notifications(now=now)
        self.assertEqual(result["sent"], 1)
        self.assertTrue(NotificationLog.objects.filter(kind=NotificationLog.Kind.CUSTOM).exists())

    @patch("core.services.notifications.send_push")
    def test_worker_sends_notification_thirty_minutes_before_exam_once(self, send_mock):
        send_mock.return_value = {"success_count": 1, "failure_count": 0, "invalid_tokens": [], "errors": []}
        now = timezone.make_aware(datetime(2026, 7, 16, 10, 31))
        first = process_due_notifications(now=now)
        second = process_due_notifications(now=now)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertTrue(NotificationLog.objects.filter(kind=NotificationLog.Kind.THIRTY_MINUTES).exists())
