from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.services.manager_auth import ManagerAuthUnavailable


@override_settings(MANAGER_SL_AUTH_TOKEN="test-token")
class ManagerSLLoginTests(TestCase):
    @patch("core.forms.authenticate_manager")
    def test_login_creates_local_shadow_account(self, manager_auth):
        manager_auth.return_value = {
            "authenticated": True,
            "username": "manager@example.com",
            "email": "manager@example.com",
            "first_name": "Олеся",
            "last_name": "Менеджер",
            "is_staff": False,
        }

        response = self.client.post(
            reverse("login"),
            {"username": "manager@example.com", "password": "ManagerPassword!"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="manager@example.com")
        self.assertEqual(user.first_name, "Олеся")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @patch("core.forms.authenticate_manager", return_value=None)
    def test_login_rejects_invalid_manager_credentials(self, manager_auth):
        response = self.client.post(
            reverse("login"),
            {"username": "manager@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email или пароль ManagerSL указаны неверно")

    @patch("core.forms.authenticate_manager", side_effect=ManagerAuthUnavailable)
    def test_login_reports_manager_unavailable(self, manager_auth):
        response = self.client.post(
            reverse("login"),
            {"username": "manager@example.com", "password": "password"},
        )
        self.assertContains(response, "ManagerSL временно не отвечает")
