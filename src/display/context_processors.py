from django.conf import settings

def firebase_settings(request):
    return {
        "FIREBASE_WEB_API_KEY": getattr(settings, "FIREBASE_WEB_API_KEY", "")
    }


def user_profile(request):
    """
    The navbar's profile menu trigger shows the logged-in user's picture (matched via
    Person.email, same lookup ContestViewSet.get_serializer_context and others already use for
    "the Person behind this request.user") when they have one, falling back to an initials avatar
    otherwise - see base_tailwind.html.
    """
    picture_url = None
    if request.user.is_authenticated:
        from display.models import Person

        person = Person.objects.filter(email=request.user.email).first()
        if person and person.picture:
            picture_url = person.picture.url
    return {"user_profile_picture_url": picture_url}


def sentry_settings(request):
    return {
        "SENTRY_DSN_FRONTEND": getattr(settings, "SENTRY_DSN_FRONTEND", ""),
        "BUILD_ID": getattr(settings, "BUILD_ID", ""),
    }
