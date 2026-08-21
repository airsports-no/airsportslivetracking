from live_tracking_map.settings import REDIS_PORT, REDIS_HOST, REDIS_PASSWORD
import redis
from django.core.management import BaseCommand

from display.default_scorecards.create_scorecards import create_scorecards


class Command(BaseCommand):

    def handle(self, *args, **options):
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, password=REDIS_PASSWORD)
        r.flushall()
        print("Flushed all Redis data")
