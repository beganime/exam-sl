from typing import Any

import requests
from django.conf import settings


class ManagerAuthUnavailable(RuntimeError):
    pass


def authenticate_manager(username: str, password: str) -> dict[str, Any] | None:
    token = str(settings.MANAGER_SL_AUTH_TOKEN or "").strip()
    endpoint = str(settings.MANAGER_SL_AUTH_URL or "").strip()
    if not endpoint or not token:
        raise ManagerAuthUnavailable("ManagerSL authentication is not configured")

    try:
        response = requests.post(
            endpoint,
            json={"username": username, "password": password},
            headers={"Authorization": f"Bearer {token}"},
            timeout=(3, settings.MANAGER_SL_AUTH_TIMEOUT),
        )
    except requests.RequestException as exc:
        raise ManagerAuthUnavailable("ManagerSL request failed") from exc

    if response.status_code == 401:
        return None
    if response.status_code != 200:
        raise ManagerAuthUnavailable(f"ManagerSL returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ManagerAuthUnavailable("ManagerSL returned invalid JSON") from exc
    return payload if payload.get("authenticated") else None
