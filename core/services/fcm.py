import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging


class FCMConfigurationError(RuntimeError):
    pass


def _resolve_path(path_value):
    path = Path(path_value)
    if not path.is_absolute():
        path = settings.BASE_DIR / path
    return path


def get_firebase_app(name="[DEFAULT]", credentials_path=None, expected_project_id=None):
    try:
        return firebase_admin.get_app(name)
    except ValueError:
        credentials_path = _resolve_path(credentials_path or settings.FIREBASE_CREDENTIALS)
        if not credentials_path.exists():
            raise FCMConfigurationError(
                f"Не найден Firebase service account JSON: {credentials_path}"
            )
        try:
            service_account = json.loads(credentials_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FCMConfigurationError(f"Firebase service account JSON повреждён: {exc}") from exc
        service_project_id = service_account.get("project_id")
        if expected_project_id and service_project_id and service_project_id != expected_project_id:
            raise FCMConfigurationError(
                "Firebase service account project_id "
                f"'{service_project_id}' не совпадает с FIREBASE_PROJECT_ID '{expected_project_id}'. "
                "Скачайте service account JSON из того же Firebase проекта, где создан Web Push certificate."
            )
        return firebase_admin.initialize_app(credentials.Certificate(str(credentials_path)), name=name)


def _project_id_for_app(app):
    return getattr(app, "project_id", "") or "unknown-project"


def _configured_firebase_credentials():
    values = [settings.FIREBASE_CREDENTIALS]
    legacy_credentials = getattr(settings, "FIREBASE_LEGACY_CREDENTIALS", "")
    if legacy_credentials:
        values.append(legacy_credentials)
    for path in sorted(settings.BASE_DIR.glob("firebase-service-account*.json")):
        values.append(str(path))

    result = []
    seen = set()
    for value in values:
        if not value:
            continue
        try:
            path = _resolve_path(value)
        except TypeError:
            continue
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def firebase_apps_for_sending():
    apps = []
    for index, credentials_path in enumerate(_configured_firebase_credentials()):
        app_name = "[DEFAULT]" if index == 0 else f"firebase-{index}"
        label = "primary" if index == 0 else credentials_path.name
        try:
            apps.append((label, get_firebase_app(app_name, credentials_path, expected_project_id=None)))
        except FCMConfigurationError as exc:
            apps.append((f"{label}-error", exc))
    return apps


def send_push(tokens, title, body, data=None, link="/"):
    clean_tokens = list(dict.fromkeys(token for token in tokens if token))
    if not clean_tokens:
        return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}
    firebase_apps = firebase_apps_for_sending()
    absolute_link = urljoin(f"{settings.SITE_URL}/", link.lstrip("/"))
    data = {str(k): str(v) for k, v in (data or {}).items()}
    data.setdefault("link", absolute_link)
    result = {"success_count": 0, "failure_count": 0, "invalid_tokens": [], "errors": []}
    for token in clean_tokens:
        webpush_kwargs = {
            "notification": messaging.WebpushNotification(icon="/static/img/push-icon.svg"),
        }
        if urlparse(absolute_link).scheme == "https":
            webpush_kwargs["fcm_options"] = messaging.WebpushFCMOptions(link=absolute_link)

        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data=data,
            webpush=messaging.WebpushConfig(**webpush_kwargs),
        )
        token_sent = False
        token_invalid = False
        token_errors = []
        for app_name, app in firebase_apps:
            if isinstance(app, FCMConfigurationError):
                token_errors.append(f"{app_name}: {app}")
                continue
            try:
                messaging.send(message, app=app)
                result["success_count"] += 1
                token_sent = True
                break
            except messaging.UnregisteredError:
                token_invalid = True
                token_errors.append(f"{app_name} ({_project_id_for_app(app)}): Браузерный FCM-токен больше не зарегистрирован.")
                break
            except messaging.SenderIdMismatchError:
                token_errors.append(f"{app_name} ({_project_id_for_app(app)}): FCM-токен создан для другого Firebase sender/project.")
                continue
            except Exception as exc:  # Firebase exposes several transport-specific exceptions.
                token_errors.append(f"{app_name} ({_project_id_for_app(app)}): {exc}")
                if "quota exceeded" in str(exc).lower():
                    continue
                break
        if token_sent:
            continue
        result["failure_count"] += 1
        if token_invalid:
            result["invalid_tokens"].append(token)
        if token_errors:
            result["errors"].append(" | ".join(token_errors))
        else:
            result["success_count"] += 1
    return result
