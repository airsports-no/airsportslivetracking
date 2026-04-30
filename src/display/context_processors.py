from django.conf import settings

def firebase_settings(request):
    return {
        "FIREBASE_WEB_API_KEY": getattr(settings, "FIREBASE_WEB_API_KEY", "")
    }
