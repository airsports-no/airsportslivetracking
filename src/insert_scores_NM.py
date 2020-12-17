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
    Contest, Task, TaskTest, TaskSummary, ContestSummary, TeamTestScore
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard

contest = Contest.objects.filter(name="NM 2020").first()

contestants = {
    "Anders": {
        "planning": 8,
        "navigation": 373,
        "observation": 320,
        "landing_one": 70,
        "landing_two": 200,
        "landing_three": 3,
        "landing_four": 246,
        "navigation_summary": 701,
        "landing_summary": 498,
        "summary": 947
    },
    "Arild": {
        "planning": 22,
        "navigation": 813,
        "observation": 420,
        "landing_one": 300,
        "landing_two": 200,
        "landing_three": 200,
        "landing_four": 30,
        "navigation_summary": 1255,
        "landing_summary": 370,
        "summary": 1620
    },
    # "Bjørn": (datetime.datetime(2020, 8, 1, 9, 15), 70, 1),
    # "Espen": (datetime.datetime(2020, 8, 1, 11, 10), 70, 1),
    # "Frank-Olaf": (datetime.datetime(2020, 8, 1, 10, 5), 75, 1),
    # "Håkon": (datetime.datetime(2020, 8, 1, 11, 15), 70, 1),
    # "Hans-Inge": (datetime.datetime(2020, 8, 1, 9, 50), 85, 2),
    # "Hedvig": (datetime.datetime(2020, 8, 1, 13, 5), 70, 2),
    # "Helge": (datetime.datetime(2020, 8, 1, 12, 55), 75, 1),
    # "Jorge": (datetime.datetime(2020, 8, 1, 9, 10), 70, 1),
    # "Jørgen": (datetime.datetime(2020, 8, 1, 10, 55), 75, 1),
    # "Kenneth": (datetime.datetime(2020, 8, 1, 9, 5), 70, 1),
    # "Magnus": (datetime.datetime(2020, 8, 1, 11, 5), 70, 2),
    # "Niklas": (datetime.datetime(2020, 8, 1, 9, 0), 75, 1),
    # "Odin": (datetime.datetime(2020, 8, 1, 9, 20), 70, 1),
    # "Ola": (datetime.datetime(2020, 8, 1, 13, 0), 70, 1),
    # "Ole": (datetime.datetime(2020, 8, 1, 10, 25), 70, 1),
    # "Steinar": (datetime.datetime(2020, 8, 1, 9, 55), 80, 2),
    # "Stian": (datetime.datetime(2020, 8, 1, 13, 10), 70, 2),
    # "Tim": (datetime.datetime(2020, 8, 1, 11, 0), 70, 2),
    # "Tommy": (datetime.datetime(2020, 8, 1, 13, 15), 70, 1),
    # "TorHelge": (datetime.datetime(2020, 8, 1, 12, 40), 70, 2)
}
aeroplane = Aeroplane.objects.first()

navigation_task = Task.objects.create(name="navigation", contest=contest, heading="Navigation")
planning_test = TaskTest.objects.create(name="planning", heading="Planning", task=navigation_task, index=0)
navigation_test = TaskTest.objects.create(name="navigation", heading="Navigation", task=navigation_task, index=1)
observation_test = TaskTest.objects.create(name="observation", heading="Observation", task=navigation_task, index=2)

landing_task = Task.objects.create(name="landing", contest=contest, heading="Landing")
landing_one = TaskTest.objects.create(name="landing_one", heading="Landing 1", task=landing_task, index=0)
landing_two = TaskTest.objects.create(name="landing_two", heading="Landing 2", task=landing_task, index=1)
landing_three = TaskTest.objects.create(name="landing_three", heading="Landing 3", task=landing_task, index=2)
landing_four = TaskTest.objects.create(name="landing_four", heading="Landing 4", task=landing_task, index=3)

for contestant_name, scores in contestants.items():
    crew, _ = Crew.objects.get_or_create(pilot=contestant_name, navigator="")
    team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane)
    for test, value in scores.items():
        if "summary" in test:
            parts = test.split("_")
            if len(parts) == 2:
                TaskSummary.objects.create(team=team, task=Task.objects.get(name=parts[0]), points=value)
            if len(parts) == 1:
                ContestSummary.objects.create(team=team, contest=contest, points=value)
        else:
            TeamTestScore.objects.create(team=team, task_test=TaskTest.objects.get(name=test), points=value)
