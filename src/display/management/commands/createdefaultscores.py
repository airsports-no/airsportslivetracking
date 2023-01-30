from django.core.management import BaseCommand

from display.default_scorecards.create_scorecards import create_scorecards


class Command(BaseCommand):

    def handle(self, *args, **options):
        create_scorecards()
