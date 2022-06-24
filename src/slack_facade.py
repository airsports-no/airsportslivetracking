import json
import logging

import requests

from live_tracking_map.settings import SLACK_DEVELOPMENT_WEBHOOK

logger = logging.getLogger(__name__)


def post_slack_message(title: str, text: str):
    """

    :param text: Slack markdown format
    :return:
    """
    block = {
        "text": title,
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
    }
    try:
        response = requests.post(
            SLACK_DEVELOPMENT_WEBHOOK,
            data=json.dumps(block),
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            logger.error(f"Failed posting message {text} to Slack: {response.text}")
    except:
        logger.exception(f"Failed posting message {text} to Slack")


if __name__ == "__main__":
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
    from display.models import Contestant

    contestant = Contestant.objects.all().first()
    post_slack_message(
        f"Calculator started for {contestant} in navigation task <https://airsports.no{contestant.navigation_task.tracking_link}|{contestant.navigation_task}>"
    )
