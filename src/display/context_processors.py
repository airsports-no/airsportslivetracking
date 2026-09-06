from django.conf import settings

def firebase_settings(request):
    return {
        "FIREBASE_WEB_API_KEY": getattr(settings, "FIREBASE_WEB_API_KEY", "")
    }


def sentry_settings(request):
    return {
        "SENTRY_DSN_FRONTEND": getattr(settings, "SENTRY_DSN_FRONTEND", ""),
        "BUILD_ID": getattr(settings, "BUILD_ID", ""),
    }
