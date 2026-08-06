import logging
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from core.models import BrowserDevice, Exam, NotificationLog
from core.services.fcm import send_push
from core.services.students_life import StudentsLifeAPIError, StudentsLifeClient


logger = logging.getLogger(__name__)

EXAM_HEADERS = (
    "ID экзамена", "Айди", "Внутренний ID", "Вуз", "Направление", "Экзамен",
    "Дата и время", "логин", "Пароль", "почта", "Место или ссылка",
    "Ответственный", "Обновлено", "Версия уведомления",
)


def quote_sheet(title):
    return "'" + str(title).replace("'", "''") + "'"


def sheets_enabled():
    return bool(
        settings.GOOGLE_SHEETS_ENABLED
        and settings.GOOGLE_SHEETS_SPREADSHEET_ID
        and settings.GOOGLE_SHEETS_CREDENTIALS_FILE
    )


class GoogleSheetsSource:
    def __init__(self):
        if not sheets_enabled():
            raise ImproperlyConfigured("Google Sheets integration is not configured.")
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SHEETS_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID

    def rows(self, sheet_name):
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet(sheet_name)}!A:ZZ",
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
        rows = result.get("values", [])
        if not rows:
            return []
        headers = rows[0]
        missing = [header for header in EXAM_HEADERS if sheet_name == settings.GOOGLE_SHEETS_EXAMS_SHEET and header not in headers]
        if missing:
            raise ValueError(f"В листе {sheet_name} отсутствуют столбцы: {', '.join(missing)}")
        return [
            {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
            for row in rows[1:]
        ]


def parse_exam_at(value):
    raw = str(value or "").strip()
    for fmt in (
        "%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M",
    ):
        try:
            return timezone.make_aware(datetime.strptime(raw, fmt), timezone.get_current_timezone())
        except ValueError:
            continue
    raise ValueError(f"Не удалось распознать дату и время: {raw}")


def integer(value, default=0):
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return default


def display_name(user):
    return (user.get_full_name() or user.username).strip().casefold()


def resolve_manager(value):
    expected = str(value or "").strip().casefold()
    if not expected:
        return None
    return next((user for user in User.objects.filter(is_active=True) if display_name(user) == expected), None)


def system_user():
    user, created = User.objects.get_or_create(
        username="exam-sheet-sync",
        defaults={"first_name": "Google Sheets", "is_active": False},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def notify_change(exam, *, created):
    tokens = set(BrowserDevice.objects.filter(is_active=True).values_list("token", flat=True))
    lookup = exam.sl_id or exam.client_email or exam.client_full_name
    if lookup:
        try:
            _, remote_tokens = StudentsLifeClient().find_tokens_for_client(lookup)
            tokens.update(item.get("token") for item in remote_tokens if item.get("token"))
        except StudentsLifeAPIError:
            logger.warning("Students Life tokens are unavailable for %s", lookup, exc_info=True)

    kind = NotificationLog.Kind.SHEET_NEW if created else NotificationLog.Kind.SHEET_UPDATED
    title = "Добавлен экзамен" if created else "Изменены дата или время экзамена"
    body = (
        f"{exam.client_full_name} · {exam.university} · "
        f"{timezone.localtime(exam.exam_at).strftime('%d.%m.%Y %H:%M')}"
    )
    if tokens:
        result = send_push(list(tokens), title, body, {"exam_id": exam.pk, "kind": kind}, exam.get_absolute_url())
        log_status = NotificationLog.Status.SENT if result["success_count"] else NotificationLog.Status.FAILED
        error = "; ".join(result.get("errors", []))
    else:
        result = {"success_count": 0, "failure_count": 0}
        log_status = NotificationLog.Status.SKIPPED
        error = "Нет активных push-токенов."
    NotificationLog.objects.update_or_create(
        exam=exam,
        recipient=None,
        kind=kind,
        scheduled_for=exam.exam_at,
        defaults={
            "status": log_status,
            "success_count": result["success_count"],
            "failure_count": result["failure_count"],
            "error": error,
        },
    )


@transaction.atomic
def sync_row(row, row_number, general_by_sl_id, notifier=notify_change):
    source_id = str(row.get("ID экзамена") or "").strip()
    if not source_id:
        return "skipped"
    sl_id = str(row.get("Айди") or "").strip()
    client = general_by_sl_id.get(sl_id, {})
    exam_at = parse_exam_at(row.get("Дата и время"))
    existing = Exam.objects.filter(source_id=source_id).first()
    date_changed = bool(existing and existing.exam_at != exam_at)
    manager = resolve_manager(row.get("Ответственный"))
    values = {
        "sl_id": sl_id,
        "source_row": row_number,
        "source_notification_version": integer(row.get("Версия уведомления")),
        "source_synced_at": timezone.now(),
        "client_full_name": str(client.get("ФИО абитуриента") or sl_id or source_id),
        "client_login": str(row.get("логин") or ""),
        "client_password": str(row.get("Пароль") or ""),
        "client_email": str(row.get("почта") or ""),
        "exam_at": exam_at,
        "university": str(row.get("Вуз") or ""),
        "program": str(row.get("Направление") or ""),
        "subject": str(row.get("Экзамен") or ""),
        "exam_url": str(row.get("Место или ссылка") or ""),
        "responsible_manager": manager,
        "created_by": existing.created_by if existing else (manager or system_user()),
    }
    exam, created = Exam.objects.update_or_create(source_id=source_id, defaults=values)
    if created or date_changed:
        transaction.on_commit(lambda: notifier(exam, created=created))
    return "created" if created else ("changed" if date_changed else "unchanged")


def sync_exams(source=None, notifier=notify_change):
    if source is None and not sheets_enabled():
        return {"status": "disabled", "created": 0, "changed": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    source = source or GoogleSheetsSource()
    general_by_sl_id = {
        str(row.get("Айди") or "").strip(): row
        for row in source.rows(settings.GOOGLE_SHEETS_GENERAL_SHEET)
        if str(row.get("Айди") or "").strip()
    }
    stats = {"created": 0, "changed": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    for row_number, row in enumerate(source.rows(settings.GOOGLE_SHEETS_EXAMS_SHEET), start=2):
        try:
            state = sync_row(row, row_number, general_by_sl_id, notifier=notifier)
            stats[state] += 1
        except Exception:
            stats["failed"] += 1
            logger.exception("Failed to sync Google Sheets exam row %s", row_number)
    return {"status": "ok" if not stats["failed"] else "partial", **stats}
