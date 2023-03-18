from django.apps import AppConfig


class DisplayConfig(AppConfig):
    name = 'display'

    def ready(self):
        # Import signal handlers
        from . import signals
