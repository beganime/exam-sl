import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import BrowserDevice, Exam, ExamComment


class AuthAndExamViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("manager", password="safe-pass-123", first_name="Марат")
        self.client.force_login(self.user)
        self.exam = Exam.objects.create(
            client_full_name="Анна Ахметова",
            client_login="anna",
            client_password="open-secret",
            exam_at=timezone.now() + timedelta(days=1),
            university="МГУ",
            subject="История",
            client_contacts="telegram @anna",
            created_by=self.user,
        )

    def test_dashboard_shows_today_or_tomorrow_exam(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Анна Ахметова")

    def test_search_matches_contacts_and_password(self):
        for query in ("telegram", "open-secret"):
            response = self.client.get(reverse("exam-list"), {"q": query})
            self.assertContains(response, "Анна Ахметова")

    def test_exam_list_is_paginated(self):
        for index in range(25):
            Exam.objects.create(
                client_full_name=f"Клиент {index}",
                exam_at=timezone.now() + timedelta(days=index + 2),
                university="Тестовый вуз",
                subject="Тестовый предмет",
                created_by=self.user,
            )
        response = self.client.get(reverse("exam-list"))
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["exams"]), 20)

    def test_inline_update_exam_from_list(self):
        response = self.client.post(
            reverse("exam-inline-update", args=[self.exam.pk]),
            {
                "client_full_name": "Анна Новая",
                "client_login": "anna-new",
                "client_password": "new-visible-pass",
                "exam_at": timezone.localtime(self.exam.exam_at).strftime("%Y-%m-%dT%H:%M"),
                "university": "СПбГУ",
                "subject": "Физика",
                "client_contacts": "telegram @new",
                "status": Exam.Status.CONFIRMED,
                "created_by": self.user.pk,
                "responsible_manager": self.user.pk,
            },
        )
        self.assertRedirects(response, reverse("exam-list"))
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.client_full_name, "Анна Новая")
        self.assertEqual(self.exam.client_login, "anna-new")
        self.assertEqual(self.exam.status, Exam.Status.CONFIRMED)
        self.assertEqual(self.exam.responsible_manager, self.user)

    def test_create_exam_can_choose_creator_and_responsible_manager(self):
        creator = User.objects.create_user("chosen-creator")
        responsible = User.objects.create_user("chosen-responsible")
        response = self.client.post(
            reverse("exam-create"),
            {
                "client_full_name": "Новый Клиент",
                "exam_at": (timezone.now() + timedelta(days=3)).astimezone().strftime("%Y-%m-%dT%H:%M"),
                "university": "КФУ",
                "subject": "Математика",
                "status": Exam.Status.PLANNED,
                "created_by": creator.pk,
                "responsible_manager": responsible.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        exam = Exam.objects.get(client_full_name="Новый Клиент")
        self.assertEqual(exam.created_by, creator)
        self.assertEqual(exam.responsible_manager, responsible)

    def test_inline_create_exam_from_table(self):
        exam_at = timezone.now() + timedelta(days=4)
        response = self.client.post(
            reverse("exam-inline-create"),
            {
                "client_full_name": "Клиент из таблицы",
                "exam_at": timezone.localtime(exam_at).strftime("%Y-%m-%dT%H:%M"),
                "university": "МГУ",
                "subject": "Физика",
                "status": Exam.Status.PLANNED,
                "created_by": self.user.pk,
                "responsible_manager": self.user.pk,
            },
        )
        self.assertRedirects(response, reverse("exam-list"))
        created = Exam.objects.get(client_full_name="Клиент из таблицы")
        self.assertEqual(created.created_by, self.user)
        self.assertEqual(created.responsible_manager, self.user)

    def test_add_comment(self):
        response = self.client.post(
            reverse("comment-add", args=[self.exam.pk]),
            {"text": "Предупредили в WhatsApp", "is_client_warned": "on"},
        )
        self.assertRedirects(response, self.exam.get_absolute_url())
        self.assertTrue(ExamComment.objects.get(exam=self.exam).is_client_warned)

    @patch("core.views.StudentsLifeClient.search_profiles", return_value=[])
    @patch("core.views.StudentsLifeClient.search_users", return_value=[])
    def test_quick_search_returns_local_results(self, users_mock, profiles_mock):
        response = self.client.get(reverse("quick-search"), {"q": "Анна"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["local"][0]["id"], self.exam.pk)

    @patch("core.views.StudentsLifeClient.register_device_token", return_value={"id": 44})
    def test_register_browser_token_and_sync(self, register_mock):
        response = self.client.post(
            reverse("push-register"),
            data=json.dumps({"token": "fcm-token", "device_id": "Chrome"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        device = BrowserDevice.objects.get(token="fcm-token")
        self.assertEqual(device.external_token_id, "44")

    @patch("core.views.send_push", return_value={"success_count": 1, "failure_count": 0, "invalid_tokens": [], "errors": []})
    @patch("core.views.StudentsLifeClient.find_tokens_for_client", return_value=(["77"], [{"token": "client-fcm-token"}]))
    def test_external_client_push_accepts_name_or_login(self, tokens_mock, send_mock):
        response = self.client.post(reverse("push-test-client"), {"client_query": "anna"})
        self.assertRedirects(response, reverse("push-settings"))
        tokens_mock.assert_called_once_with("anna")
        send_mock.assert_called_once()

    def test_service_worker_is_served_at_root_scope(self):
        response = self.client.get(reverse("firebase-messaging-sw"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertContains(response, "firebase.messaging")

    @patch("core.views.send_push", return_value={"success_count": 1, "failure_count": 0, "invalid_tokens": [], "errors": []})
    def test_test_push_can_target_selected_manager(self, send_mock):
        selected = User.objects.create_user("selected-manager")
        BrowserDevice.objects.create(user=selected, token="selected-token")
        response = self.client.post(reverse("push-test"), {"recipients": [selected.pk]})
        self.assertRedirects(response, reverse("push-settings"))
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.args[0], ["selected-token"])
