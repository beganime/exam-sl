from django.conf import settings


def app_settings(request):
    return {
        "firebase_web_config": settings.FIREBASE_WEB_CONFIG,
        "fcm_vapid_public_key": settings.FCM_VAPID_PUBLIC_KEY,
        "fcm_server_configured": bool(settings.FIREBASE_CREDENTIALS),
    }
