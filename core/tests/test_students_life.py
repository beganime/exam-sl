from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from core.services.students_life import StudentsLifeClient


class StudentsLifeClientTests(SimpleTestCase):
    @override_settings(
        STUDENTSLIFE_API_BASE="https://students-life.test/api/v1",
        STUDENTSLIFE_API_KEY="service-key",
        STUDENTSLIFE_BEARER_TOKEN="",
        STUDENTSLIFE_REFRESH_TOKEN="",
        STUDENTSLIFE_TOKEN_FILE="",
    )
    @patch("core.services.students_life.requests.request")
    def test_service_api_key_can_read_device_tokens(self, request_mock):
        response = Mock(status_code=200, content=b'{"results":[]}')
        response.json.return_value = {"results": []}
        response.raise_for_status.return_value = None
        request_mock.return_value = response

        self.assertEqual(StudentsLifeClient().list_device_tokens(), [])

        headers = request_mock.call_args.kwargs["headers"]
        self.assertEqual(headers["X-API-KEY"], "service-key")
        self.assertNotIn("Authorization", headers)

    @override_settings(
        STUDENTSLIFE_API_BASE="https://students-life.test/api/v1",
        STUDENTSLIFE_API_KEY="",
        STUDENTSLIFE_BEARER_TOKEN="old-access",
        STUDENTSLIFE_REFRESH_TOKEN="refresh-token",
        STUDENTSLIFE_TOKEN_FILE="",
    )
    @patch("core.services.students_life.requests.post")
    @patch("core.services.students_life.requests.request")
    def test_refreshes_access_token_once_after_401(self, request_mock, post_mock):
        unauthorized = Mock(status_code=401, content=b'{"detail":"expired"}')
        unauthorized.raise_for_status.side_effect = RuntimeError("expired")
        ok = Mock(status_code=200, content=b'{"results":[]}')
        ok.json.return_value = {"results": []}
        ok.raise_for_status.return_value = None
        request_mock.side_effect = [unauthorized, ok]

        refresh = Mock(status_code=200)
        refresh.json.return_value = {"access": "new-access", "refresh": "new-refresh"}
        refresh.raise_for_status.return_value = None
        post_mock.return_value = refresh

        client = StudentsLifeClient()
        self.assertEqual(client.list_device_tokens(), [])
        self.assertEqual(client.bearer_token, "new-access")
        self.assertEqual(client.refresh_token, "new-refresh")
        self.assertEqual(request_mock.call_count, 2)
        self.assertEqual(request_mock.call_args.kwargs["headers"]["Authorization"], "Bearer new-access")
