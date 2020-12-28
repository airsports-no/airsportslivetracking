# coding: utf-8
import datetime
import glob
import os

from traccar_facade import Traccar

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from display.models import Team, Aeroplane, NavigationTask, Route, Contestant, Scorecard, TraccarCredentials, Crew, \
    Contest, Task, TaskTest, TaskSummary, ContestSummary, TeamTestScore, Person, ContestTeam
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard

contest = Contest.objects.get(pk=59)
for contestant in Contestant.objects.filter(navigation_task__contest=contest):
    ContestTeam.objects.create(contest=contest, team=contestant.team, tracking_service=contestant.tracking_service,
                               tracker_device_id=contestant.tracker_device_id, air_speed=contestant.air_speed)
