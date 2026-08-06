from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class ManagerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="manager_profile")
    display_name = models.CharField("Имя менеджера", max_length=180, blank=True)
    phone = models.CharField("Телефон", max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.user.get_full_name() or self.user.username


class Exam(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирован"
        CONFIRMED = "confirmed", "Подтверждён"
        COMPLETED = "completed", "Завершён"
        CANCELLED = "cancelled", "Отменён"

    client_full_name = models.CharField("ФИО клиента", max_length=255, db_index=True)
    sl_id = models.CharField("SL-ID", max_length=32, blank=True, db_index=True)
    source_id = models.CharField("ID строки источника", max_length=120, unique=True, null=True, blank=True)
    source_row = models.PositiveIntegerField("Строка Google Sheets", null=True, blank=True)
    source_notification_version = models.PositiveIntegerField("Версия уведомления", default=0)
    source_synced_at = models.DateTimeField("Синхронизировано", null=True, blank=True)
    client_login = models.CharField("Логин", max_length=255, blank=True)
    client_password = models.CharField("Пароль", max_length=255, blank=True)
    client_email = models.EmailField("Почта", blank=True)
    exam_at = models.DateTimeField("Дата и время экзамена", db_index=True)
    university = models.CharField("Вуз", max_length=255, db_index=True)
    subject = models.CharField("Название предмета", max_length=255, db_index=True)
    program = models.CharField("Направление", max_length=255, blank=True)
    client_source = models.CharField("Откуда клиент", max_length=255, blank=True)
    client_contacts = models.TextField("Контакты клиента", blank=True)
    exam_url = models.URLField("Ссылка на экзамен", max_length=1000, blank=True)
    custom_notify_at = models.DateTimeField("Дополнительное время уведомления", null=True, blank=True)
    external_user_id = models.CharField("ID клиента в Students Life", max_length=80, blank=True, db_index=True)
    external_profile_id = models.CharField("ID профиля в Students Life", max_length=80, blank=True)
    notification_recipients = models.ManyToManyField(
        User, verbose_name="Получатели уведомлений", related_name="assigned_exams", blank=True
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.PLANNED)
    responsible_manager = models.ForeignKey(
        User,
        verbose_name="Ответственный",
        on_delete=models.SET_NULL,
        related_name="responsible_exams",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_exams")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["exam_at"]

    def __str__(self):
        return f"{self.client_full_name} — {self.subject}"

    def get_absolute_url(self):
        return reverse("exam-detail", args=[self.pk])


class ExamComment(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    text = models.TextField("Комментарий", max_length=2000)
    is_client_warned = models.BooleanField("Клиент предупреждён", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class BrowserDevice(models.Model):
    class Platform(models.TextChoices):
        WEB = "web", "Web"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="browser_devices")
    token = models.TextField(unique=True)
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.WEB)
    device_id = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    external_token_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} · {self.device_id or 'браузер'}"


class NotificationLog(models.Model):
    class Kind(models.TextChoices):
        MORNING = "day_before_08", "За день, 08:00"
        EVENING = "day_before_20", "За день, 20:00"
        THIRTY_MINUTES = "before_30_minutes", "За 30 минут"
        CUSTOM = "custom", "Дополнительное"
        TEST = "test", "Тестовое"
        SHEET_NEW = "sheet_new", "Новый экзамен из Google Sheets"
        SHEET_UPDATED = "sheet_updated", "Изменение экзамена в Google Sheets"

    class Status(models.TextChoices):
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"
        SKIPPED = "skipped", "Пропущено"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="notification_logs", null=True, blank=True)
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=30, choices=Kind.choices)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "recipient", "kind", "scheduled_for"],
                name="unique_scheduled_exam_notification",
            )
        ]
        ordering = ["-created_at"]
