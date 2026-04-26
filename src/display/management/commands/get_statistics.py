from django.core.management.base import BaseCommand
from display.utilities.statistics_utilities import get_system_statistics
import json

class Command(BaseCommand):
    help = 'Displays system-wide statistics for contestants and competitions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output statistics in JSON format',
        )

    def handle(self, *args, **options):
        stats = get_system_statistics()

        if options['json']:
            self.stdout.write(json.dumps(stats, indent=4))
            return

        self.stdout.write(self.style.SUCCESS('--- System Statistics ---'))
        self.stdout.write(f'Total Persons: {stats["number_of_persons"]}')
        self.stdout.write(f'Total Contests: {stats["number_of_contests"]}')
        self.stdout.write(f'Total Tasks: {stats["number_of_tasks"]}')
        self.stdout.write(f'Total Contestants: {stats["number_of_contestants"]}')
        self.stdout.write(f'Started Contestants: {stats["number_of_started_contestants"]}')
        self.stdout.write(f'Contestants Crossed Starting: {stats["number_of_contestants_crossed_starting"]}')
        self.stdout.write(f'Persons Crossed Starting: {stats["number_of_persons_crossed_starting"]}')

        self.stdout.write(self.style.SUCCESS('\n--- Scale & Performance ---'))
        self.stdout.write(f'Total GPS Positions Stored: {stats["total_gps_positions"]:,}')
        self.stdout.write(f'Total Penalties (Anomalies): {stats["total_anomalies"]:,}')
        self.stdout.write(f'Average Air Speed: {stats["average_air_speed"]:.1f} kt')

        self.stdout.write(self.style.MIGRATE_LABEL('\n--- Top 5 Aircraft Types ---'))
        for item in stats["top_aircraft_types"]:
            self.stdout.write(f'{item["type"] or "Unknown"}: {item["count"]}')

        self.stdout.write(self.style.MIGRATE_LABEL('\n--- Top 5 Most Active Clubs ---'))
        for item in stats["top_clubs"]:
            self.stdout.write(f'{item["name"]}: {item["count"]}')

        self.stdout.write(self.style.MIGRATE_LABEL('\n--- Tasks per Country ---'))
        for country, count in stats["navigation_task_per_country"]:
            self.stdout.write(f'{country}: {count}')

        self.stdout.write(self.style.MIGRATE_LABEL('\n--- Contests per Country ---'))
        for country, count in stats["contest_per_country"]:
            self.stdout.write(f'{country}: {count}')
