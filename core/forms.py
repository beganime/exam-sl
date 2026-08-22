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
    client_lookup = forms.ChoiceField(label="Клиент из листа «Общее»", choices=(), required=False)

    class Meta:
        model = Exam
        fields = (
            "client_lookup",
            "client_full_name",
            "sl_id",
            "client_login",
            "client_password",
            "exam_at",
            "university",
            "subject",
            "exam_url",
            "status",
            "responsible_manager",
            "created_by",
        )
        widgets = {
            "client_full_name": forms.HiddenInput,
            "sl_id": forms.HiddenInput,
            "exam_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "client_password": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["client_full_name"].required = False
        self.fields["sl_id"].required = False
        user_queryset = User.objects.order_by("first_name", "last_name", "username")
        self.fields["responsible_manager"].queryset = user_queryset
        self.fields["created_by"].queryset = user_queryset
        choices = [("", "Выберите клиента")]
        self.client_records = {}
        try:
            from .services.google_sheets import GoogleSheetsSource, sheets_enabled
            if sheets_enabled():
                for row in GoogleSheetsSource().general_clients():
                    full_name = str(row.get("ФИО абитуриента") or "").strip()
                    sl_id = str(row.get("Айди") or "").strip()
                    if not full_name:
                        continue
                    key = sl_id or full_name
                    self.client_records[key] = row
                    choices.append((key, f"{full_name}{' · ' + sl_id if sl_id else ''}"))
        except Exception:
            self.client_records = {}
        self.fields["client_lookup"].choices = choices
        if self.instance.pk:
            current_key = self.instance.sl_id or self.instance.client_full_name
            if current_key and current_key not in dict(choices):
                choices.append((current_key, f"{self.instance.client_full_name} · {self.instance.sl_id}".strip(" ·")))
            self.initial["client_lookup"] = current_key

    def clean(self):
        cleaned = super().clean()
        key = cleaned.get("client_lookup")
        row = getattr(self, "client_records", {}).get(key)
        if row:
            cleaned["client_full_name"] = str(row.get("ФИО абитуриента") or "").strip()
            cleaned["sl_id"] = str(row.get("Айди") or "").strip()
        if not cleaned.get("client_full_name"):
            self.add_error("client_lookup", "Выберите клиента из листа «Общее».")
        return cleaned

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
