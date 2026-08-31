from live_tracking_map.settings import REDIS_PORT, REDIS_HOST, REDIS_PASSWORD
import redis
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = (
        "Wipe the entire Redis instance (FLUSHALL) - not just the Django cache DB. This also "
        "destroys the Celery broker queue, the Channels websocket layer, every live-calculator "
        "heartbeat, and all queued position data. During a live contest this can split "
        "calculators (duplicate processing) and drop every connected spectator."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            self.stdout.write(
                self.style.WARNING(
                    "This will FLUSHALL every Redis database on this host, including the "
                    "Celery broker, the Channels layer, live-calculator heartbeats, and queued "
                    "position data - not just the Django cache."
                )
            )
            confirm = input("Type 'yes' to continue, or anything else to abort: ")
            if confirm != "yes":
                self.stdout.write(self.style.ERROR("Aborted."))
                return
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, password=REDIS_PASSWORD)
        r.flushall()
        self.stdout.write(self.style.SUCCESS("Flushed all Redis data"))
