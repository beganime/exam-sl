import logging
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import BrowserDevice, Exam, NotificationLog
from core.services.fcm import send_push
from core.services.students_life import StudentsLifeAPIError, StudentsLifeClient


logger = logging.getLogger(__name__)

EXAM_HEADERS = (
    "ID экзамена", "Айди", "ФИО клиента", "Внутренний ID", "Вуз", "Направление", "Экзамен",
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
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
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

    def general_clients(self):
        return self.rows(settings.GOOGLE_SHEETS_GENERAL_SHEET)

    def prepare_exam_sheet(self):
        metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        sheets = {item["properties"]["title"]: item["properties"] for item in metadata.get("sheets", [])}
        general = sheets.get(settings.GOOGLE_SHEETS_GENERAL_SHEET)
        if not general:
            raise ValueError(f"Лист {settings.GOOGLE_SHEETS_GENERAL_SHEET} не найден.")
        exams = sheets.get(settings.GOOGLE_SHEETS_EXAMS_SHEET)
        if not exams:
            response = self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": settings.GOOGLE_SHEETS_EXAMS_SHEET}}}]},
            ).execute()
            exams = response["replies"][0]["addSheet"]["properties"]

        general_headers = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet(settings.GOOGLE_SHEETS_GENERAL_SHEET)}!1:1",
        ).execute().get("values", [[]])[0]
        try:
            name_column = general_headers.index("ФИО абитуриента")
        except ValueError as exc:
            raise ValueError("В листе «Общее» отсутствует столбец «ФИО абитуриента».") from exc

        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"{quote_sheet(settings.GOOGLE_SHEETS_EXAMS_SHEET)}!A1:O1",
            valueInputOption="RAW",
            body={"values": [list(EXAM_HEADERS)]},
        ).execute()
        column_letter = _column_letter(name_column + 1)
        exam_sheet_id = exams["sheetId"]
        requests = [
            {"updateSheetProperties": {"properties": {"sheetId": exam_sheet_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {"range": {"sheetId": exam_sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(EXAM_HEADERS)}, "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1}, "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}, "bold": True}, "horizontalAlignment": "CENTER"}}, "fields": "userEnteredFormat"}},
            {"updateDimensionProperties": {"range": {"sheetId": exam_sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": 2000}, "properties": {"pixelSize": 34}, "fields": "pixelSize"}},
            {"setDataValidation": {"range": {"sheetId": exam_sheet_id, "startRowIndex": 1, "endRowIndex": 2000, "startColumnIndex": 2, "endColumnIndex": 3}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"='{settings.GOOGLE_SHEETS_GENERAL_SHEET}'!${column_letter}$2:${column_letter}$2000"}]}, "strict": True, "showCustomUi": True}}},
        ]
        for index in (0, 1, 3):
            requests.append({"updateDimensionProperties": {"range": {"sheetId": exam_sheet_id, "dimension": "COLUMNS", "startIndex": index, "endIndex": index + 1}, "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        ).execute()
        return {"sheet": settings.GOOGLE_SHEETS_EXAMS_SHEET, "client_column": "ФИО клиента"}


def _column_letter(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


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


def _next_retry_at(attempt_count):
    max_attempts = max(settings.SHEET_NOTIFICATION_MAX_ATTEMPTS, 1)
    if attempt_count >= max_attempts:
        return None
    base = max(settings.SHEET_NOTIFICATION_RETRY_BASE_SECONDS, 30)
    delay = min(base * (2 ** max(attempt_count - 1, 0)), 6 * 60 * 60)
    return timezone.now() + timedelta(seconds=delay)


def students_exam_payload(exam):
    local_exam = timezone.localtime(exam.exam_at)
    return {
        "subject": exam.subject or "Экзамен",
        "university": exam.university or "Экзамен",
        "exam_date": local_exam.date().isoformat(),
        "exam_time": local_exam.time().replace(microsecond=0).isoformat(),
        "timezone": str(settings.TIME_ZONE),
        "comment": "",
        "manager_sl_exam_id": exam.source_id or f"exam-sl-{exam.pk}",
        "is_active": exam.status != Exam.Status.CANCELLED,
    }


def sync_exam_to_students_life(exam, lookup):
    if not lookup:
        return 0
    students = StudentsLifeClient()
    delivered = 0
    for user_id in students.resolve_user_ids(lookup):
        result = students.upsert_client_exam(user_id, students_exam_payload(exam))
        external_exam_id = str(result.get("id") or "")
        if external_exam_id and exam.external_exam_id != external_exam_id:
            Exam.objects.filter(pk=exam.pk).update(external_exam_id=external_exam_id)
            exam.external_exam_id = external_exam_id
        delivered += 1
    return delivered


def notify_change(exam, *, created, log=None):
    kind = NotificationLog.Kind.SHEET_NEW if created else NotificationLog.Kind.SHEET_UPDATED
    if log is None:
        log = NotificationLog.objects.create(
            exam=exam,
            recipient=None,
            kind=kind,
            scheduled_for=timezone.now(),
            status=NotificationLog.Status.PENDING,
        )
    if log.status == NotificationLog.Status.SENT:
        return {"status": "sent", "success_count": log.success_count, "failure_count": log.failure_count}

    log.attempt_count += 1
    in_app_success_count = 0
    tokens = set(BrowserDevice.objects.filter(is_active=True).values_list("token", flat=True))
    lookup = exam.sl_id or exam.client_email or exam.client_full_name
    if lookup:
        try:
            in_app_success_count = sync_exam_to_students_life(exam, lookup)
        except StudentsLifeAPIError:
            logger.warning("Students Life exam sync is unavailable for %s", lookup, exc_info=True)

    title = "Добавлен экзамен" if created else "Изменены дата или время экзамена"
    body = (
        f"{exam.client_full_name} · {exam.university} · "
        f"{timezone.localtime(exam.exam_at).strftime('%d.%m.%Y %H:%M')}"
    )
    firebase_paths = [
        Path(value) for value in (settings.FIREBASE_CREDENTIALS, settings.FIREBASE_LEGACY_CREDENTIALS)
        if str(value or "").strip()
    ]
    firebase_configured = any(path.is_file() for path in firebase_paths)
    if in_app_success_count and (not firebase_configured or not tokens):
        log.status = NotificationLog.Status.SENT
        log.success_count = in_app_success_count
        log.failure_count = 0
        log.error = ""
        log.next_retry_at = None
        log.save(update_fields=[
            "status", "success_count", "failure_count", "error",
            "attempt_count", "next_retry_at",
        ])
        return {
            "status": log.status,
            "success_count": log.success_count,
            "failure_count": log.failure_count,
            "attempt_count": log.attempt_count,
        }

    try:
        if not tokens:
            raise RuntimeError("Нет активных push-токенов менеджеров или клиента.")
        result = send_push(list(tokens), title, body, {"exam_id": exam.pk, "kind": kind}, exam.get_absolute_url())
        log.success_count = in_app_success_count + result.get("success_count", 0)
        log.failure_count = result.get("failure_count", 0)
        log.error = "; ".join(result.get("errors", []))
        if not log.success_count:
            raise RuntimeError(log.error or "Firebase не доставил уведомление ни на одно устройство.")
        BrowserDevice.objects.filter(token__in=result.get("invalid_tokens", [])).update(is_active=False)
        log.status = NotificationLog.Status.SENT
        log.next_retry_at = None
    except Exception as exc:
        log.status = NotificationLog.Status.FAILED
        log.error = str(exc)[:4000]
        log.next_retry_at = _next_retry_at(log.attempt_count)
        logger.warning(
            "Exam change notification failed for exam %s (attempt %s).",
            exam.pk,
            log.attempt_count,
            exc_info=True,
        )
    log.save(
        update_fields=[
            "status",
            "success_count",
            "failure_count",
            "error",
            "attempt_count",
            "next_retry_at",
        ]
    )
    return {
        "status": log.status,
        "success_count": log.success_count,
        "failure_count": log.failure_count,
        "attempt_count": log.attempt_count,
    }


def retry_failed_change_notifications(now=None, limit=100):
    now = now or timezone.now()
    max_attempts = max(settings.SHEET_NOTIFICATION_MAX_ATTEMPTS, 1)
    logs = list(
        NotificationLog.objects.select_related("exam")
        .filter(
            kind__in=[NotificationLog.Kind.SHEET_NEW, NotificationLog.Kind.SHEET_UPDATED],
            status__in=[NotificationLog.Status.PENDING, NotificationLog.Status.FAILED],
            attempt_count__lt=max_attempts,
        )
        .filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now))
        .order_by("created_at")[:max(int(limit), 1)]
    )
    stats = {"sent": 0, "failed": 0}
    for log in logs:
        result = notify_change(
            log.exam,
            created=log.kind == NotificationLog.Kind.SHEET_NEW,
            log=log,
        )
        stats["sent" if result["status"] == NotificationLog.Status.SENT else "failed"] += 1
    return stats


@transaction.atomic
def sync_row(row, row_number, general_by_sl_id, notifier=notify_change):
    source_id = str(row.get("ID экзамена") or f"sheet-row-{row_number}").strip()
    sl_id = str(row.get("Айди") or "").strip()
    client_name = str(row.get("ФИО клиента") or "").strip()
    client = general_by_sl_id.get(sl_id, {}) or general_by_sl_id.get(client_name.casefold(), {})
    exam_at = parse_exam_at(row.get("Дата и время"))
    existing = Exam.objects.filter(source_id=source_id).first()
    date_changed = bool(existing and existing.exam_at != exam_at)
    manager = resolve_manager(row.get("Ответственный"))
    values = {
        "sl_id": sl_id,
        "source_row": row_number,
        "source_notification_version": integer(row.get("Версия уведомления")),
        "source_synced_at": timezone.now(),
        "client_full_name": str(client.get("ФИО абитуриента") or client_name or sl_id or source_id),
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
    general_by_sl_id = {}
    for row in source.rows(settings.GOOGLE_SHEETS_GENERAL_SHEET):
        sl_id = str(row.get("Айди") or "").strip()
        full_name = str(row.get("ФИО абитуриента") or "").strip()
        if sl_id:
            general_by_sl_id[sl_id] = row
        if full_name:
            general_by_sl_id[full_name.casefold()] = row
    stats = {"created": 0, "changed": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    for row_number, row in enumerate(source.rows(settings.GOOGLE_SHEETS_EXAMS_SHEET), start=2):
        try:
            state = sync_row(row, row_number, general_by_sl_id, notifier=notifier)
            stats[state] += 1
        except Exception:
            stats["failed"] += 1
            logger.exception("Failed to sync Google Sheets exam row %s", row_number)
    return {"status": "ok" if not stats["failed"] else "partial", **stats}
