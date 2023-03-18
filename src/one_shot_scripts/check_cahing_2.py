import json
import logging
import os
from typing import List, TYPE_CHECKING

from django.core.cache import cache

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

    cache.delete_pattern("test*")
    print(cache.get("test_r"))
