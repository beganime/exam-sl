from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import Exam, ManagerProfile, NotificationLog
from core.services.notifications import notification_slots, recipients_for_exam


class ExamModelTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("manager", password="safe-pass-123")
        self.exam_at = timezone.make_aware(datetime(2026, 7, 20, 14, 30))
        self.exam = Exam.objects.create(
            client_full_name="Анна Ахметова",
            client_login="anna-login",
            client_password="visible-pass",
            exam_at=self.exam_at,
            university="МГУ",
            subject="Математика",
            created_by=self.manager,
        )

    def test_profile_created_for_new_manager(self):
        self.assertTrue(ManagerProfile.objects.filter(user=self.manager).exists())

    def test_fixed_slots_include_previous_day_and_thirty_minutes_before(self):
        slots = dict(notification_slots(self.exam))
        morning = timezone.localtime(slots[NotificationLog.Kind.MORNING])
        evening = timezone.localtime(slots[NotificationLog.Kind.EVENING])
        thirty_minutes = timezone.localtime(slots[NotificationLog.Kind.THIRTY_MINUTES])
        self.assertEqual(morning.date(), timezone.localtime(self.exam_at).date() - timedelta(days=1))
        self.assertEqual(morning.time(), time(8, 0))
        self.assertEqual(evening.time(), time(20, 0))
        self.assertEqual(thirty_minutes, timezone.localtime(self.exam_at) - timedelta(minutes=30))

    def test_empty_recipients_means_all_active_managers(self):
        second = User.objects.create_user("second")
        self.assertCountEqual(recipients_for_exam(self.exam), [self.manager, second])

    def test_selected_recipients_limit_delivery(self):
        selected = User.objects.create_user("selected")
        User.objects.create_user("not-selected")
        self.exam.notification_recipients.add(selected)
        self.assertCountEqual(recipients_for_exam(self.exam), [selected])
