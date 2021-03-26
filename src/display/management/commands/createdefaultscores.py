from django.core.management import BaseCommand

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import TraccarCredentials


class Command(BaseCommand):

    def handle(self, *args, **options):
        create_scorecards()
        TraccarCredentials.objects.get_or_create()
