import logging
import os
import sys

from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from display.models import Contestant
from display.calculators.calculator_factory import calculator_factory

if __name__ == "__main__":
    contestant_pk = sys.argv[1]
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        # Contestant has been deleted, gracefully terminate
        sys.exit(0)
    if not contestant.contestanttrack.calculator_finished:
        calculator = calculator_factory(contestant, live_processing=True)
        calculator.run()
    else:
        logger.warning(
            f"Attempting to start new calculator for terminated contestant {contestant}"
        )
