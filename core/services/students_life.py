import json as jsonlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from django.conf import settings


class StudentsLifeAPIError(RuntimeError):
    pass


class StudentsLifeEndpointUnavailable(StudentsLifeAPIError):
    pass


@dataclass
class StudentsLifeClient:
    api_key: str = ""
    bearer_token: str = ""
    refresh_token: str = ""
    token_file: str = ""

    def __post_init__(self):
        self.api_key = self.api_key or settings.STUDENTSLIFE_API_KEY
        self.bearer_token = self.bearer_token or settings.STUDENTSLIFE_BEARER_TOKEN
        self.refresh_token = self.refresh_token or settings.STUDENTSLIFE_REFRESH_TOKEN
        self.token_file = self.token_file or settings.STUDENTSLIFE_TOKEN_FILE
        self.base_url = settings.STUDENTSLIFE_API_BASE
        self._load_tokens_from_file()

    def _token_path(self):
        if not self.token_file:
            return None
        path = Path(self.token_file)
        if not path.is_absolute():
            path = settings.BASE_DIR / path
        return path

    def _load_tokens_from_file(self):
        path = self._token_path()
        if not path or not path.exists():
            return
        try:
            payload = jsonlib.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, jsonlib.JSONDecodeError):
            return
        self.bearer_token = payload.get("access") or self.bearer_token
        self.refresh_token = payload.get("refresh") or self.refresh_token
        self.base_url = (payload.get("base_url") or self.base_url).rstrip("/")

    def _save_tokens_to_file(self):
        path = self._token_path()
        if not path:
            return
        payload = {}
        if path.exists():
            try:
                payload = jsonlib.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, jsonlib.JSONDecodeError):
                payload = {}
        payload.update(
            {
                "base_url": self.base_url,
                "access": self.bearer_token,
                "refresh": self.refresh_token,
            }
        )
        path.write_text(jsonlib.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def refresh_access_token(self):
        if not self.refresh_token:
            raise StudentsLifeAPIError("Для обновления access нужен STUDENTSLIFE_REFRESH_TOKEN или studentslife-token.json.")
        try:
            response = requests.post(
                f"{self.base_url}/auth/refresh/",
                json={"refresh": self.refresh_token},
                timeout=12,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            if getattr(exc, "response", None) is not None:
                detail = f" Ответ API: {exc.response.text[:300]}"
            raise StudentsLifeAPIError(f"Не удалось обновить Students Life access token: {exc}.{detail}") from exc
        payload = response.json()
        self.bearer_token = payload.get("access") or self.bearer_token
        self.refresh_token = payload.get("refresh") or self.refresh_token
        self._save_tokens_to_file()
        return self.bearer_token

    def _headers(self, bearer_required=False):
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif self.api_key and not bearer_required:
            headers["X-API-KEY"] = self.api_key
        if bearer_required and not self.bearer_token:
            raise StudentsLifeAPIError("Для этого метода нужен STUDENTSLIFE_BEARER_TOKEN.")
        return headers

    def _request(self, method: str, path: str, *, params=None, json=None, bearer_required=False, retry=True) -> Any:
        try:
            response = requests.request(
                method,
                f"{self.base_url}/{path.lstrip('/')}",
                headers=self._headers(bearer_required=bearer_required),
                params=params,
                json=json,
                timeout=12,
            )
            if response.status_code == 401 and bearer_required and retry and self.refresh_token:
                self.refresh_access_token()
                return self._request(
                    method,
                    path,
                    params=params,
                    json=json,
                    bearer_required=bearer_required,
                    retry=False,
                )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = ""
            if getattr(exc, "response", None) is not None:
                detail = f" Ответ API: {exc.response.text[:300]}"
            raise StudentsLifeAPIError(f"Students Life API недоступен: {exc}.{detail}") from exc
        return response.json() if response.content else None

    @staticmethod
    def _items(payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            value = payload.get("results", payload.get("data", []))
            if isinstance(value, dict):
                value = value.get("results", value.get("items", []))
            return value if isinstance(value, list) else []
        return []

    def search_users(self, query: str, limit: int = 20):
        try:
            payload = self._request(
                "GET",
                "accounts/users/",
                params={"search": query, "limit": limit},
                bearer_required=not bool(self.api_key),
            )
        except StudentsLifeAPIError as exc:
            if "404 Client Error" in str(exc):
                raise StudentsLifeEndpointUnavailable("Students Life API сейчас не отдаёт /accounts/users/ (404).") from exc
            raise
        return self._items(payload)

    def search_profiles(self, query: str, limit: int = 20):
        try:
            payload = self._request(
                "GET",
                "accounts/client-profiles/",
                params={"search": query, "limit": limit},
                bearer_required=not bool(self.api_key),
            )
        except StudentsLifeAPIError as exc:
            if "404 Client Error" in str(exc):
                raise StudentsLifeEndpointUnavailable("Students Life API сейчас не отдаёт /accounts/client-profiles/ (404).") from exc
            raise
        return self._items(payload)

    def list_device_tokens(self):
        payload = self._request(
            "GET",
            "notifications/device-tokens/",
            bearer_required=not bool(self.api_key),
        )
        return self._items(payload)

    def register_device_token(self, token: str, device_id: str):
        return self._request(
            "POST",
            "notifications/device-tokens/",
            json={"token": token, "platform": "web", "device_id": device_id, "is_active": True},
            bearer_required=not bool(self.api_key),
        )

    def delete_device_token(self, token_id: str):
        return self._request(
            "DELETE",
            f"notifications/device-tokens/{token_id}/",
            bearer_required=not bool(self.api_key),
        )

    def find_tokens_for_user(self, user_id: str):
        user_id = str(user_id)
        tokens = self.list_device_tokens()
        result = []
        for item in tokens:
            owner = item.get("user") or item.get("user_id") or item.get("owner")
            owner_id = owner.get("id") if isinstance(owner, dict) else owner
            if owner_id is not None and str(owner_id) == user_id and item.get("is_active", True):
                result.append(item)
        return result

    @staticmethod
    def _extract_user_id(item):
        user = item.get("user")
        if isinstance(user, dict):
            return user.get("id")
        if user:
            return user
        return item.get("user_id") or item.get("id")

    @staticmethod
    def _extract_profile_user_id(profile):
        user = profile.get("user")
        if isinstance(user, dict):
            return user.get("id")
        return user or profile.get("user_id")

    def resolve_user_ids(self, query: str, limit: int = 20):
        query = str(query).strip()
        if not query:
            return []

        user_ids = []
        if query.isdigit():
            return [query]

        unavailable = []
        try:
            for user in self.search_users(query, limit=limit):
                user_id = self._extract_user_id(user)
                if user_id is not None:
                    user_ids.append(str(user_id))
        except StudentsLifeEndpointUnavailable as exc:
            unavailable.append(str(exc))

        try:
            for profile in self.search_profiles(query, limit=limit):
                user_id = self._extract_profile_user_id(profile)
                if user_id is not None:
                    user_ids.append(str(user_id))
        except StudentsLifeEndpointUnavailable as exc:
            unavailable.append(str(exc))

        if unavailable and not user_ids:
            raise StudentsLifeEndpointUnavailable(
                "Поиск клиента по имени/email недоступен: "
                + " ".join(unavailable)
                + " Нужен рабочий endpoint пользователей/профилей или owner-поле в /notifications/device-tokens/."
            )

        return list(dict.fromkeys(user_ids))

    def find_tokens_for_client(self, query: str, limit: int = 20):
        user_ids = self.resolve_user_ids(query, limit=limit)
        if not user_ids:
            return [], []

        wanted = set(user_ids)
        matched_tokens = []
        for item in self.list_device_tokens():
            owner = item.get("user") or item.get("user_id") or item.get("owner")
            owner_id = owner.get("id") if isinstance(owner, dict) else owner
            if owner_id is not None and str(owner_id) in wanted and item.get("is_active", True):
                matched_tokens.append(item)
        return user_ids, matched_tokens
