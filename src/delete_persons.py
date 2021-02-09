import os
from datetime import datetime, timezone


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django
    django.setup()

from display.models import Contest, Crew, Team, Person

Contest.objects.all().delete()
Team.objects.all().delete()
Crew.objects.all().delete()
Person.objects.all().delete()