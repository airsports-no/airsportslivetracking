from django.apps import AppConfig


class DisplayConfig(AppConfig):
    name = 'display'

    def ready(self):
        # Import signal handlers
        from . import signals

        # Register drf-spectacular customizations (e.g. FirebaseAuthenticationScheme)
        from . import schema  # noqa: F401

        # settings.FRONTEND_ROUTES is read from routes.json once, at start-up: have the development server restart when
        # it changes, as it does for Python files, or a new SPA route links to "/" until the next restart
        from django.utils.autoreload import autoreload_started

        autoreload_started.connect(_watch_frontend_routes)


def _watch_frontend_routes(sender, **kwargs):
    from django.conf import settings

    sender.watch_dir(settings.BASE_DIR.parent / "react_vite" / "src", "routes.json")
