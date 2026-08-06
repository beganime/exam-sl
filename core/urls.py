from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.dashboard, name="dashboard"),
    path("login/", views.ManagerLoginView.as_view(), name="login"),
    path("logout/", views.ManagerLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("exams/", views.ExamListView.as_view(), name="exam-list"),
    path("exams/new/", views.ExamCreateView.as_view(), name="exam-create"),
    path("exams/inline-create/", views.inline_create_exam, name="exam-inline-create"),
    path("exams/<int:pk>/", views.ExamDetailView.as_view(), name="exam-detail"),
    path("exams/<int:pk>/edit/", views.ExamUpdateView.as_view(), name="exam-update"),
    path("exams/<int:pk>/inline/", views.inline_update_exam, name="exam-inline-update"),
    path("exams/<int:pk>/delete/", views.ExamDeleteView.as_view(), name="exam-delete"),
    path("exams/<int:pk>/comments/", views.add_comment, name="comment-add"),
    path("search/quick/", views.quick_search, name="quick-search"),
    path("push/", views.push_settings, name="push-settings"),
    path("push/register/", views.register_push_token, name="push-register"),
    path("push/<int:pk>/delete/", views.delete_push_token, name="push-delete"),
    path("push/test/", views.test_own_push, name="push-test"),
    path("push/test-client/", views.test_external_client_push, name="push-test-client"),
    path("firebase-messaging-sw.js", views.firebase_messaging_service_worker, name="firebase-messaging-sw"),
]
