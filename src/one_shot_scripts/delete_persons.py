import os
from datetime import datetime, timezone


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django
    django.setup()

from display.models import Contest, Crew, Team, Person, Aeroplane

aeroplane = Aeroplane.objects.create(registration = "test")
aeroplane.delete()
aeroplane.refresh_from_db()
print(aeroplane.pk)