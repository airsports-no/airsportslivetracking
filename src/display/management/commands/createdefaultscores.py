from django.core.management import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        import display.default_scorecards.default_scorecard_fai_precision_2020
