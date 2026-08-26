from pathlib import Path

import environ


BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="unsafe-dev-key-change-me")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost","*", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "examsl.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.app_settings",
            ],
        },
    }
]
WSGI_APPLICATION = "examsl.wsgi.application"
ASGI_APPLICATION = "examsl.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Ashgabat"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

STUDENTSLIFE_API_BASE = env("STUDENTSLIFE_API_BASE", default="https://students-life.ru/api2/api/v1").rstrip("/")
STUDENTSLIFE_API_KEY = env("STUDENTSLIFE_API_KEY", default="")
STUDENTSLIFE_BEARER_TOKEN = env("STUDENTSLIFE_BEARER_TOKEN", default="")
STUDENTSLIFE_REFRESH_TOKEN = env("STUDENTSLIFE_REFRESH_TOKEN", default="")
STUDENTSLIFE_TOKEN_FILE = env("STUDENTSLIFE_TOKEN_FILE", default=str(BASE_DIR / "studentslife-token.json"))
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000").rstrip("/")
FIREBASE_CREDENTIALS = env("FIREBASE_CREDENTIALS", default=str(BASE_DIR / "firebase-service-account.json"))
FIREBASE_LEGACY_CREDENTIALS = env("FIREBASE_LEGACY_CREDENTIALS", default="")
FCM_VAPID_PUBLIC_KEY = env("FCM_VAPID_PUBLIC_KEY", default="")
FIREBASE_WEB_CONFIG = {
    "apiKey": env("FIREBASE_API_KEY", default="AIzaSyDTqjXb37bzfvjR0GTPQgayZG7hdeGsxN8"),
    "authDomain": env("FIREBASE_AUTH_DOMAIN", default="students-life-pushes.firebaseapp.com"),
    "projectId": env("FIREBASE_PROJECT_ID", default="students-life-pushes"),
    "storageBucket": env("FIREBASE_STORAGE_BUCKET", default="students-life-pushes.firebasestorage.app"),
    "messagingSenderId": env("FIREBASE_MESSAGING_SENDER_ID", default="980186028832"),
    "appId": env("FIREBASE_APP_ID", default="1:980186028832:web:ea1e16230c9c9aaedd5545"),
    "measurementId": env("FIREBASE_MEASUREMENT_ID", default="G-P4E4ZSPHBB"),
}

MANAGER_REGISTRATION_ENABLED = env.bool("MANAGER_REGISTRATION_ENABLED", default=False)
MANAGER_SL_AUTH_URL = env(
    "MANAGER_SL_AUTH_URL",
    default="https://manager-sl.ru/api/internal/exam/auth/",
)
MANAGER_SL_AUTH_TOKEN = env("MANAGER_SL_AUTH_TOKEN", default="")
MANAGER_SL_AUTH_TIMEOUT = env.int("MANAGER_SL_AUTH_TIMEOUT", default=10)
GOOGLE_SHEETS_ENABLED = env.bool("GOOGLE_SHEETS_ENABLED", default=False)
GOOGLE_SHEETS_SPREADSHEET_ID = env("GOOGLE_SHEETS_SPREADSHEET_ID", default="")
GOOGLE_SHEETS_CREDENTIALS_FILE = env("GOOGLE_SHEETS_CREDENTIALS_FILE", default="")
GOOGLE_SHEETS_EXAMS_SHEET = env("GOOGLE_SHEETS_EXAMS_SHEET", default="Экзамены")
GOOGLE_SHEETS_GENERAL_SHEET = env("GOOGLE_SHEETS_GENERAL_SHEET", default="Общее")
GOOGLE_SHEETS_POLL_SECONDS = env.int("GOOGLE_SHEETS_POLL_SECONDS", default=60)
SHEET_NOTIFICATION_MAX_ATTEMPTS = env.int("SHEET_NOTIFICATION_MAX_ATTEMPTS", default=12)
SHEET_NOTIFICATION_RETRY_BASE_SECONDS = env.int("SHEET_NOTIFICATION_RETRY_BASE_SECONDS", default=300)
