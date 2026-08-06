import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import ExamCommentForm, ExamForm, ExamInlineForm, ManagerRegistrationForm
from .models import BrowserDevice, Exam, NotificationLog
from .services.fcm import send_push
from .services.students_life import StudentsLifeAPIError, StudentsLifeClient, StudentsLifeEndpointUnavailable


SEARCH_FIELDS = (
    "client_full_name",
    "client_login",
    "client_password",
    "university",
    "subject",
    "client_source",
    "client_contacts",
    "external_user_id",
    "external_profile_id",
    "created_by__username",
    "created_by__first_name",
    "created_by__last_name",
    "responsible_manager__username",
    "responsible_manager__first_name",
    "responsible_manager__last_name",
)


def apply_exam_search(queryset, query):
    if not query:
        return queryset
    search = Q()
    for field in SEARCH_FIELDS:
        search |= Q(**{f"{field}__icontains": query})
    search |= Q(comments__text__icontains=query)
    return queryset.filter(search).distinct()


class ManagerLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class ManagerLogoutView(LogoutView):
    pass


def register(request):
    if not settings.MANAGER_REGISTRATION_ENABLED:
        return JsonResponse({"detail": "Регистрация менеджеров отключена."}, status=403)
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = ManagerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Аккаунт менеджера создан. Теперь подключите уведомления.")
        return redirect("push-settings")
    return render(request, "registration/register.html", {"form": form})


def health(request):
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unhealthy", "database": "unavailable"}, status=503)
    return JsonResponse({
        "status": "ok",
        "database": "ok",
        "google_sheets_enabled": settings.GOOGLE_SHEETS_ENABLED,
    })


@login_required
def dashboard(request):
    now = timezone.localtime()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    active = Exam.objects.exclude(status__in=[Exam.Status.CANCELLED, Exam.Status.COMPLETED])
    today_exams = active.filter(exam_at__date=today).prefetch_related("comments")
    tomorrow_exams = active.filter(exam_at__date=tomorrow).prefetch_related("comments")
    upcoming = active.filter(exam_at__gt=now).order_by("exam_at")[:6]
    return render(
        request,
        "core/dashboard.html",
        {
            "today_exams": today_exams,
            "tomorrow_exams": tomorrow_exams,
            "upcoming": upcoming,
            "today_count": today_exams.count(),
            "tomorrow_count": tomorrow_exams.count(),
            "active_count": active.filter(exam_at__gte=now).count(),
            "device_count": request.user.browser_devices.filter(is_active=True).count(),
        },
    )


class ExamListView(LoginRequiredMixin, ListView):
    model = Exam
    template_name = "core/exam_list.html"
    context_object_name = "exams"
    paginate_by = 20

    def get_queryset(self):
        queryset = Exam.objects.select_related("created_by", "responsible_manager").prefetch_related("notification_recipients")
        queryset = apply_exam_search(queryset, self.request.GET.get("q", "").strip())
        status = self.request.GET.get("status")
        if status in Exam.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["status"] = self.request.GET.get("status", "")
        context["status_choices"] = Exam.Status.choices
        context["user_choices"] = User.objects.order_by("first_name", "last_name", "username")
        query = self.request.GET.copy()
        query.pop("page", None)
        context["page_query"] = query.urlencode()
        return context


class ExamCreateView(LoginRequiredMixin, CreateView):
    model = Exam
    form_class = ExamForm
    template_name = "core/exam_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["created_by"] = self.request.user
        initial["responsible_manager"] = self.request.user
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Экзамен добавлен.")
        return response


class ExamUpdateView(LoginRequiredMixin, UpdateView):
    model = Exam
    form_class = ExamForm
    template_name = "core/exam_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Данные экзамена обновлены.")
        return response


class ExamDeleteView(LoginRequiredMixin, DeleteView):
    model = Exam
    template_name = "core/exam_confirm_delete.html"
    success_url = reverse_lazy("exam-list")

    def form_valid(self, form):
        messages.success(self.request, "Экзамен удалён.")
        return super().form_valid(form)


@login_required
@require_POST
def inline_create_exam(request):
    form = ExamInlineForm(request.POST)
    if form.is_valid():
        exam = form.save()
        messages.success(request, f"Экзамен «{exam.client_full_name}» добавлен в таблицу.")
    else:
        first_error = next(iter(form.errors.values()))[0]
        messages.error(request, f"Не удалось добавить строку: {first_error}")
    redirect_to = request.POST.get("next") or reverse_lazy("exam-list")
    return redirect(redirect_to)


@login_required
@require_POST
def inline_update_exam(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    form = ExamInlineForm(request.POST, instance=exam)
    if form.is_valid():
        form.save()
        messages.success(request, f"Экзамен «{exam.client_full_name}» сохранён.")
    else:
        first_error = next(iter(form.errors.values()))[0]
        messages.error(request, f"Не удалось сохранить строку: {first_error}")
    redirect_to = request.POST.get("next") or reverse_lazy("exam-list")
    return redirect(redirect_to)


class ExamDetailView(LoginRequiredMixin, DetailView):
    model = Exam
    template_name = "core/exam_detail.html"
    context_object_name = "exam"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comment_form"] = ExamCommentForm()
        return context


@login_required
@require_POST
def add_comment(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    form = ExamCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.exam = exam
        comment.author = request.user
        comment.save()
        messages.success(request, "Комментарий добавлен.")
    else:
        messages.error(request, "Не удалось добавить комментарий.")
    return redirect(exam)


@login_required
def quick_search(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"local": [], "users": [], "profiles": []})
    local = apply_exam_search(Exam.objects.all(), query)[:8]
    payload = {
        "local": [
            {
                "id": exam.pk,
                "name": exam.client_full_name,
                "subject": exam.subject,
                "university": exam.university,
                "exam_at": timezone.localtime(exam.exam_at).strftime("%d.%m.%Y %H:%M"),
                "url": exam.get_absolute_url(),
            }
            for exam in local
        ],
        "users": [],
        "profiles": [],
    }
    try:
        api = StudentsLifeClient()
        if not (api.api_key or api.bearer_token):
            raise StudentsLifeAPIError("Добавьте STUDENTSLIFE_API_KEY или STUDENTSLIFE_BEARER_TOKEN в .env.")
        with ThreadPoolExecutor(max_workers=2) as pool:
            users_future = pool.submit(api.search_users, query, 8)
            profiles_future = pool.submit(api.search_profiles, query, 8)
            payload["users"] = users_future.result()
            payload["profiles"] = profiles_future.result()
    except StudentsLifeAPIError as exc:
        payload["api_error"] = str(exc)
    return JsonResponse(payload)


@login_required
def push_settings(request):
    return render(
        request,
        "core/push_settings.html",
        {
            "devices": request.user.browser_devices.order_by("-updated_at"),
            "push_recipients": User.objects.filter(is_active=True).order_by("first_name", "username"),
        },
    )


@login_required
@require_POST
def register_push_token(request):
    try:
        data = json.loads(request.body)
        token = data["token"].strip()
        device_id = data.get("device_id", "browser")[:255]
    except (json.JSONDecodeError, KeyError, AttributeError):
        return JsonResponse({"ok": False, "error": "Некорректные данные токена."}, status=400)
    if not token:
        return JsonResponse({"ok": False, "error": "Пустой токен."}, status=400)
    device, _ = BrowserDevice.objects.update_or_create(
        token=token,
        defaults={"user": request.user, "device_id": device_id, "platform": "web", "is_active": True},
    )
    sync_error = ""
    try:
        remote = StudentsLifeClient().register_device_token(token, device_id)
        if isinstance(remote, dict) and remote.get("id"):
            device.external_token_id = str(remote["id"])
            device.save(update_fields=["external_token_id"])
    except StudentsLifeAPIError as exc:
        sync_error = str(exc)
    return JsonResponse({"ok": True, "sync_error": sync_error})


@login_required
@require_POST
def delete_push_token(request, pk):
    device = get_object_or_404(BrowserDevice, pk=pk, user=request.user)
    sync_error = ""
    if device.external_token_id:
        try:
            StudentsLifeClient().delete_device_token(device.external_token_id)
        except StudentsLifeAPIError as exc:
            sync_error = str(exc)
    device.delete()
    if sync_error:
        messages.warning(request, f"Локальный токен удалён, но API не ответил: {sync_error}")
    else:
        messages.success(request, "Устройство отключено.")
    return redirect("push-settings")


@login_required
@require_POST
def test_own_push(request):
    recipient_ids = request.POST.getlist("recipients")
    recipients = User.objects.filter(is_active=True, pk__in=recipient_ids) if recipient_ids else User.objects.filter(pk=request.user.pk)
    if not recipients.exists():
        messages.error(request, "Выберите хотя бы одного получателя.")
        return redirect("push-settings")
    try:
        sent = failed = skipped = 0
        for recipient in recipients:
            tokens = list(recipient.browser_devices.filter(is_active=True).values_list("token", flat=True))
            if not tokens:
                skipped += 1
                NotificationLog.objects.create(
                    recipient=recipient, kind=NotificationLog.Kind.TEST,
                    status=NotificationLog.Status.SKIPPED,
                    error="Нет активного браузерного push-токена.",
                )
                continue
            result = send_push(
                tokens,
                "Тест ExamSL",
                f"Тестовое уведомление для {recipient.get_full_name() or recipient.username} доставлено.",
                link="/",
            )
            success = result["success_count"] > 0
            sent += int(success)
            failed += int(not success)
            NotificationLog.objects.create(
                recipient=recipient,
                kind=NotificationLog.Kind.TEST,
                status=NotificationLog.Status.SENT if success else NotificationLog.Status.FAILED,
                success_count=result["success_count"],
                failure_count=result["failure_count"],
                error="; ".join(result.get("errors", [])),
            )
            BrowserDevice.objects.filter(token__in=result["invalid_tokens"]).update(is_active=False)
        if sent:
            messages.success(request, f"Тест отправлен: {sent}. Без токена: {skipped}. Ошибок: {failed}.")
        else:
            messages.error(request, f"Ни одно уведомление не отправлено. Без токена: {skipped}, ошибок FCM: {failed}.")
    except Exception as exc:
        messages.error(request, f"Ошибка FCM: {exc}")
    return redirect("push-settings")


@login_required
@require_POST
def test_external_client_push(request):
    client_query = request.POST.get("client_query", "").strip()
    if not client_query:
        messages.error(request, "Укажите имя, логин, телефон или ID клиента Students Life.")
        return redirect("push-settings")
    try:
        user_ids, remote_tokens = StudentsLifeClient().find_tokens_for_client(client_query)
        tokens = [item.get("token") for item in remote_tokens if item.get("token")]
        if not user_ids:
            messages.warning(request, "Клиент не найден в базе Students Life по этому запросу.")
            return redirect("push-settings")
        if not tokens:
            messages.warning(
                request,
                "Клиент найден, но токены не найдены. API токенов должен возвращать user/user_id/owner, чтобы связать токен с клиентом.",
            )
        else:
            result = send_push(tokens, "Тест ExamSL", "Ваше тестовое уведомление успешно отправлено.")
            if result["success_count"]:
                messages.success(request, f"Отправлено на устройств: {result['success_count']}.")
            else:
                detail = "; ".join(result.get("errors", [])) or "Firebase не вернул подробность ошибки."
                messages.error(request, f"FCM не принял уведомление клиента: {detail}")
    except StudentsLifeEndpointUnavailable as exc:
        messages.warning(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Не удалось отправить: {exc}")
    return redirect("push-settings")


def firebase_messaging_service_worker(request):
    config = json.dumps(settings.FIREBASE_WEB_CONFIG)
    source = f'''importScripts("https://www.gstatic.com/firebasejs/12.16.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/12.16.0/firebase-messaging-compat.js");
firebase.initializeApp({config});
const messaging = firebase.messaging();
messaging.onBackgroundMessage((payload) => {{
  const notification = payload.notification || {{}};
  const link = (payload.data && payload.data.link) || "/";
  self.registration.showNotification(notification.title || "ExamSL", {{
    body: notification.body || "Новое уведомление",
    icon: "/static/img/push-icon.svg",
    data: {{ link }}
  }});
}});
self.addEventListener("notificationclick", (event) => {{
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.link || "/"));
}});'''
    response = HttpResponse(source, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response
