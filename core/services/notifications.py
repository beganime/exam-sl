from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from core.models import BrowserDevice, Exam, NotificationLog
from core.services.fcm import send_push


def notification_slots(exam: Exam):
    local_exam = timezone.localtime(exam.exam_at)
    previous_day = local_exam.date() - timedelta(days=1)
    tz = timezone.get_current_timezone()
    slots = [
        (NotificationLog.Kind.MORNING, timezone.make_aware(datetime.combine(previous_day, time(8, 0)), tz)),
        (NotificationLog.Kind.EVENING, timezone.make_aware(datetime.combine(previous_day, time(20, 0)), tz)),
        (NotificationLog.Kind.THIRTY_MINUTES, exam.exam_at - timedelta(minutes=30)),
    ]
    if exam.custom_notify_at:
        slots.append((NotificationLog.Kind.CUSTOM, exam.custom_notify_at))
    return slots


def recipients_for_exam(exam: Exam):
    selected = exam.notification_recipients.filter(is_active=True)
    return selected if selected.exists() else User.objects.filter(is_active=True)


def process_due_notifications(now=None, lookback_minutes=10):
    now = now or timezone.now()
    lower_bound = now - timedelta(minutes=lookback_minutes)
    stats = {"sent": 0, "failed": 0, "skipped": 0}
    exams = Exam.objects.exclude(status__in=[Exam.Status.CANCELLED, Exam.Status.COMPLETED]).filter(
        Q(exam_at__gte=now - timedelta(days=1), exam_at__lte=now + timedelta(days=2))
        | Q(custom_notify_at__gte=lower_bound, custom_notify_at__lte=now)
    )
    for exam in exams.prefetch_related("notification_recipients"):
        for kind, scheduled_for in notification_slots(exam):
            if not (lower_bound <= scheduled_for <= now):
                continue
            for recipient in recipients_for_exam(exam):
                try:
                    log, created = NotificationLog.objects.get_or_create(
                        exam=exam,
                        recipient=recipient,
                        kind=kind,
                        scheduled_for=scheduled_for,
                        defaults={"status": NotificationLog.Status.SKIPPED},
                    )
                except IntegrityError:
                    continue
                if not created:
                    continue
                tokens = list(
                    recipient.browser_devices.filter(is_active=True).values_list("token", flat=True)
                )
                if not tokens:
                    log.error = "У менеджера нет активного браузерного push-токена."
                    log.save(update_fields=["error"])
                    stats["skipped"] += 1
                    continue
                try:
                    local_time = timezone.localtime(exam.exam_at).strftime("%d.%m в %H:%M")
                    is_soon = kind == NotificationLog.Kind.THIRTY_MINUTES
                    result = send_push(
                        tokens,
                        "Экзамен через 30 минут" if is_soon else "Экзамен уже завтра",
                        f"{exam.client_full_name} · {exam.subject} · {local_time}",
                        {"exam_id": exam.pk, "kind": kind},
                        exam.get_absolute_url(),
                    )
                    BrowserDevice.objects.filter(token__in=result["invalid_tokens"]).update(is_active=False)
                    log.success_count = result["success_count"]
                    log.failure_count = result["failure_count"]
                    log.error = "; ".join(result.get("errors", []))
                    log.status = (
                        NotificationLog.Status.SENT
                        if result["success_count"]
                        else NotificationLog.Status.FAILED
                    )
                    stats["sent" if result["success_count"] else "failed"] += 1
                    log.save()
                except Exception as exc:
                    log.status = NotificationLog.Status.FAILED
                    log.error = str(exc)
                    log.save(update_fields=["status", "error"])
                    stats["failed"] += 1
    return stats
