import datetime
from display.models.contestant import Contestant
from display.models.contestant_track import ContestantTrack
from display.models.flymaster_data import FlymasterData
from display.models.navigation_task import NavigationTask
from display.tasks import recalculate_live_data_for_contestant

# navigation_tasks = [2285, 2286]
navigation_tasks=[2295,2296,2281,2282]
navigation_tasks=[2296,2281,2282]
for task in navigation_tasks:
    for c in NavigationTask.objects.get(pk=task).contestant_set.all():
        c.reset_track_and_score()
        recalculate_live_data_for_contestant.apply_async((c.pk,))


NavigationTask.objects.get(pk=2272).delete()

for c in NavigationTask.objects.get(pk=2296).contestant_set.all():
    # c.tracker_start_time = c.tracker_start_time - datetime.timedelta(minutes=1, seconds=54)
    # c.takeoff_time = c.takeoff_time - datetime.timedelta(minutes=1)
    # c.minutes_to_starting_point = 0
    # c.predefined_gate_times = None
    c.finished_by_time = c.gate_times["FP"] + datetime.timedelta(minutes=5, seconds=2)
    c.save()

new_task1 = NavigationTask.objects.get(pk=2295)
for c in NavigationTask.objects.get(pk=2272).contestant_set.all():
    c.navigation_task = new_task1
    c.save()

new_task2 = NavigationTask.objects.get(pk=2296)
for c in NavigationTask.objects.get(pk=2273).contestant_set.all():
    c.navigation_task = new_task2
    c.save()


# a = FlymasterData.objects.all().first()
# print(a.identifier)
# print(a.timestamp)
# print(a.data)


def check_gates_in_tracking_time(contestant: Contestant):
    for name, timestamp in contestant.gate_times.items():
        if not contestant.tracker_start_time < timestamp < contestant.finished_by_time:
            print(
                f"{contestant}: The waypoint {name} with timestamp {timestamp} is outside the tracking time {contestant.tracker_start_time}-{contestant.finished_by_time}"
            )


c: Contestant
for c in NavigationTask.objects.get(pk=2282).contestant_set.all():
    check_gates_in_tracking_time(c)
