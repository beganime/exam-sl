from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Exam, ExamComment


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class ManagerRegistrationForm(UserCreationForm):
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Телефон", max_length=80, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            user.manager_profile.display_name = user.get_full_name()
            user.manager_profile.phone = self.cleaned_data["phone"]
            user.manager_profile.save()
        return user


class ExamForm(forms.ModelForm):
    notify_all_managers = forms.BooleanField(
        label="Уведомить всех менеджеров",
        required=False,
        help_text="Если включено, выбранные получатели ниже не учитываются.",
    )

    class Meta:
        model = Exam
        fields = (
            "client_full_name",
            "client_login",
            "client_password",
            "exam_at",
            "university",
            "subject",
            "client_source",
            "client_contacts",
            "exam_url",
            "custom_notify_at",
            "external_user_id",
            "external_profile_id",
            "status",
            "responsible_manager",
            "created_by",
            "notify_all_managers",
            "notification_recipients",
        )
        widgets = {
            "exam_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "custom_notify_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "client_contacts": forms.Textarea(attrs={"rows": 3}),
            "notification_recipients": forms.CheckboxSelectMultiple,
            "client_password": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["custom_notify_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["notification_recipients"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "username"
        )
        user_queryset = User.objects.order_by("first_name", "last_name", "username")
        self.fields["responsible_manager"].queryset = user_queryset
        self.fields["created_by"].queryset = user_queryset
        if self.instance.pk:
            self.initial["notify_all_managers"] = not self.instance.notification_recipients.exists()

    def save(self, commit=True):
        exam = super().save(commit=commit)
        if commit and self.cleaned_data.get("notify_all_managers"):
            exam.notification_recipients.clear()
        return exam


class ExamInlineForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = (
            "client_full_name",
            "client_login",
            "client_password",
            "exam_at",
            "university",
            "subject",
            "client_source",
            "client_contacts",
            "exam_url",
            "status",
            "responsible_manager",
            "created_by",
        )
        widgets = {
            "exam_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "client_password": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        user_queryset = User.objects.order_by("first_name", "last_name", "username")
        self.fields["responsible_manager"].queryset = user_queryset
        self.fields["created_by"].queryset = user_queryset


class ExamCommentForm(forms.ModelForm):
    class Meta:
        model = ExamComment
        fields = ("text", "is_client_warned")
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Например: предупредили в WhatsApp…"})}


class LoginForm(forms.Form):
    username = forms.CharField(label="Логин")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)
