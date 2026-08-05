from django.contrib import admin

from .models import BrowserDevice, Exam, ExamComment, ManagerProfile, NotificationLog


class ExamCommentInline(admin.TabularInline):
    model = ExamComment
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("client_full_name", "subject", "university", "exam_at", "status", "responsible_manager", "created_by")
    list_filter = ("status", "exam_at", "university")
    search_fields = ("client_full_name", "client_login", "university", "subject", "client_contacts")
    filter_horizontal = ("notification_recipients",)
    inlines = [ExamCommentInline]


admin.site.register(ManagerProfile)
admin.site.register(BrowserDevice)
admin.site.register(NotificationLog)
