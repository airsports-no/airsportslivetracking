import datetime
import logging
from functools import wraps
from random import choice
from string import ascii_uppercase, ascii_lowercase, digits

from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.signals import post_save, post_delete, pre_delete, pre_save, m2m_changed
from django.dispatch import receiver

from django.core.cache import cache
from display.flight_order_and_maps.map_plotter_shared_utilities import country_code_to_map_source
from display.models import (
    TeamTestScore,
    TaskSummary,
    ContestSummary,
    Task,
    TaskTest,
    ContestTeam,
    Contestant,
    ContestantTrack,
    ScoreLogEntry,
    Crew,
    Club,
    Route,
    Photo,
    NavigationTask,
    FlightOrderConfiguration,
    TRACKING_DEVICE,
    Person,
    MyUser,
    EditableRoute,
    Contest,
)
from display.models.scorecard_and_gate_score import Scorecard
from display.utilities.traccar_factory import get_traccar_instance
from display.utilities.tracking_definitions import TrackingService

logger = logging.getLogger(__name__)


def invalidate_contest_list_cache(sender, **kwargs):
    try:
        # Use a timestamp-based base to ensure that after a cache clear or redeploy,
        # the version doesn't restart at 1. This prevents ETags from matching
        # old stale data cached in CDNs or browsers.
        version = cache.get("contest_list_version")
        if version is None:
            # Initialize with current timestamp (e.g., 1713960000)
            new_version = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        else:
            new_version = int(version) + 1

        cache.set("contest_list_version", new_version, timeout=None)
        logger.debug(f"Updated contest_list_version to {new_version} due to change in {sender}")
    except Exception as e:
        logger.error(f"Failed to update contest_list_version: {e}")
        # Fallback to current timestamp if increment fails
        cache.set("contest_list_version", int(datetime.datetime.now(datetime.timezone.utc).timestamp()), timeout=None)


@receiver(post_save, sender=Contest)
@receiver(post_delete, sender=Contest)
@receiver(post_save, sender=NavigationTask)
@receiver(post_delete, sender=NavigationTask)
@receiver(post_save, sender=ContestTeam)
@receiver(post_delete, sender=ContestTeam)
@receiver(post_save, sender=Contestant)
@receiver(post_delete, sender=Contestant)
def invalid_cache_handler(sender, **kwargs):
    invalidate_contest_list_cache(sender, **kwargs)


def prevent_recursion(func):
    @wraps(func)
    def no_recursion(sender, instance=None, **kwargs):
        if not instance:
            return

        if hasattr(instance, "_dirty"):
            return

        func(sender, instance=instance, **kwargs)

        try:
            instance._dirty = True
            instance.save()
        finally:
            del instance._dirty

    return no_recursion


def queue_team_test_score_update(instance: TeamTestScore):
    from websocket_channels import WebsocketFacade

    contest = instance.task_test.task.contest
    team_id = instance.team_id
    task_id = instance.task_test.task_id
    task_test_id = instance.task_test_id
    score_id = instance.pk

    def send_update():
        ws = WebsocketFacade()
        ws.transmit_score_update(
            contest=contest,
            team_id=team_id,
            task_id=task_id,
            task_test_id=task_test_id,
            score_id=score_id,
        )

    transaction.on_commit(send_update)




@receiver(post_delete, sender=Photo)
def auto_delete_file_on_delete(sender, instance: Photo, **kwargs):
    """
    Deletes file from filesystem
    when corresponding Photo object is deleted.
    """
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_save, sender=TaskTest)
def update_score_on_test_configuration_change(sender, instance: TaskTest, **kwargs):
    for team_test_score in instance.teamtestscore_set.all():
        auto_summarise_tests(sender, team_test_score, **kwargs)


@receiver(post_save, sender=TeamTestScore)
@receiver(post_delete, sender=TeamTestScore)
def auto_summarise_tests(sender, instance: TeamTestScore, **kwargs):
    try:
        if instance.task_test.task.autosum_scores:
            task_summary = TaskSummary.objects.filter(task=instance.task_test.task, team=instance.team).first()
            if task_summary is None:
                task_summary = TaskSummary(task=instance.task_test.task, team=instance.team, points=instance.points)
                task_summary._skip_results_broadcast = True
                try:
                    task_summary.save()
                except IntegrityError:
                    task_summary = TaskSummary.objects.get(task=instance.task_test.task, team=instance.team)
            task_summary._skip_results_broadcast = True
            task_summary.update_sum()
    except ObjectDoesNotExist:
        pass


@receiver(post_save, sender=Task)
def update_score_on_task_configuration_change(sender, instance: Task, **kwargs):
    for task_summary in instance.tasksummary_set.all():
        auto_summarise_tasks(sender, task_summary, **kwargs)


@receiver(post_save, sender=TaskSummary)
@receiver(post_delete, sender=TaskSummary)
def auto_summarise_tasks(sender, instance: TaskSummary, **kwargs):
    try:
        if instance.task.contest.autosum_scores:
            for task in Task.objects.filter(contest=instance.task.contest):
                if task.id == instance.task_id:
                    continue
                task_summary = TaskSummary.objects.filter(task=task, team=instance.team).first()
                if task_summary is None:
                    tests = TeamTestScore.objects.filter(team=instance.team, task_test__task=task)
                    if not tests.exists():
                        continue
                    task_summary = TaskSummary(task=task, team=instance.team, points=0)
                    task_summary._skip_results_broadcast = True
                    try:
                        task_summary.save()
                    except IntegrityError:
                        task_summary = TaskSummary.objects.get(task=task, team=instance.team)
                    task_summary._skip_results_broadcast = True
                    task_summary.update_sum()

            contest_summary = ContestSummary.objects.filter(contest=instance.task.contest, team=instance.team).first()
            if contest_summary is None:
                contest_summary = ContestSummary(contest=instance.task.contest, team=instance.team, points=instance.points)
                contest_summary._skip_results_broadcast = True
                try:
                    contest_summary.save()
                except IntegrityError:
                    contest_summary = ContestSummary.objects.get(contest=instance.task.contest, team=instance.team)
            contest_summary._skip_results_broadcast = True
            contest_summary.update_sum()
            # Update contestants
            from websocket_channels import WebsocketFacade

            ws = WebsocketFacade()
            for c in instance.team.contestant_set.filter(navigation_task__contest=instance.task.contest):
                ws.transmit_basic_information(c)
    except ObjectDoesNotExist:
        pass


@receiver(pre_delete, sender=Task)
def update_contest_summary_on_task_delete(sender, instance: Task, **kwargs):
    for contest_summary in ContestSummary.objects.filter(contest=instance.contest):
        contest_summary.update_sum()


@receiver(pre_delete, sender=TaskTest)
def update_task_summary_on_task_test_delete(sender, instance: TaskTest, **kwargs):
    try:
        for task_summary in TaskSummary.objects.filter(task=instance.task):
            task_summary.update_sum()
    except ObjectDoesNotExist:
        # tasktest deleted already
        pass


@receiver(post_save, sender=ContestTeam)
@receiver(post_delete, sender=ContestTeam)
def post_contest_team_change(sender, instance: ContestTeam, **kwargs):
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    ws.transmit_teams(instance.contest)

@receiver(post_save, sender=TeamTestScore)
@receiver(post_delete, sender=TeamTestScore)
def post_team_test_score_change(sender, instance: TeamTestScore, **kwargs):
    try:
        queue_team_test_score_update(instance)
    except ObjectDoesNotExist:
        pass



@receiver(post_save, sender=TaskSummary)
@receiver(post_delete, sender=TaskSummary)
def post_task_summary_change(sender, instance: TaskSummary, **kwargs):
    from websocket_channels import WebsocketFacade

    if getattr(instance, "_skip_results_broadcast", False):
        return

    def send_update():
        ws = WebsocketFacade()
        ws.transmit_contest_results(None, instance.task.contest)

    transaction.on_commit(send_update)



@receiver(post_save, sender=ContestSummary)
@receiver(post_delete, sender=ContestSummary)
def push_contest_summary_change(sender, instance: ContestSummary, **kwargs):
    from websocket_channels import WebsocketFacade

    if getattr(instance, "_skip_results_broadcast", False):
        return

    def send_update():
        ws = WebsocketFacade()
        ws.transmit_contest_results(None, instance.contest)

    transaction.on_commit(send_update)


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def push_task_change(sender, instance: Task, **kwargs):
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    ws.transmit_tasks(instance.contest)


@receiver(post_save, sender=Task)
def update_task_index(sender, instance: Task, created, **kwargs):
    if created:
        if instance.contest.task_set.all().count() > 0:
            highest_index = max([item.index for item in instance.contest.task_set.all()])
            instance.index = highest_index + 1
            instance.save()


@receiver(post_save, sender=TaskTest)
def update_task_test_index(sender, instance: TaskTest, created, **kwargs):
    if created:
        if instance.task.tasktest_set.all().count() > 0:
            highest_index = max([item.index for item in instance.task.tasktest_set.all()])
            instance.index = highest_index + 1
            instance._skip_results_broadcast = True
            try:
                instance.save()
            finally:
                del instance._skip_results_broadcast


@receiver(post_save, sender=TaskTest)
@receiver(post_delete, sender=TaskTest)
def push_test_change(sender, instance: TaskTest, **kwargs):
    from websocket_channels import WebsocketFacade

    if getattr(instance, "_skip_results_broadcast", False):
        return

    def send_update():
        ws = WebsocketFacade()
        ws.transmit_contest_results(None, instance.task.contest)

    transaction.on_commit(send_update)


#
#
# @receiver(post_save, sender=ContestTeam)
# def populate_team_results(sender, instance: ContestTeam, **kwargs):
#     for task in Task.objects.filter(contest=instance.contest):
#         TaskSummary.objects.create(team=instance.team, task=task, points=0)
#     for task_test in TaskTest.objects.filter(
#             task__contest=instance.contest):
#         TeamTestScore.objects.create(team=instance.team, task=task_test)
#     ContestSummary.objects.create(team=instance.team, contest=instance.contest, points=0)


@receiver(post_save, sender=Contestant)
def create_contestant_track_if_not_exists(sender, instance: Contestant, **kwargs):
    ContestantTrack.objects.get_or_create(
        contestant=instance, defaults={"score": instance.navigation_task.scorecard.initial_score}
    )
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    ws.transmit_contestant(instance)


@receiver(pre_save, sender=Contestant)
def validate_contestant(sender, instance: Contestant, **kwargs):
    instance.clean()


@receiver(pre_save, sender=Contestant)
def delete_flight_order_and_gate_times_if_changed(sender, instance: Contestant, **kwargs):
    if instance.pk:
        if previous_version := Contestant.objects.filter(pk=instance.pk).first():
            if (
                previous_version.starting_point_time != instance.starting_point_time
                or previous_version.wind_speed != instance.wind_speed
                or previous_version.wind_direction != instance.wind_direction
                or previous_version.air_speed != instance.air_speed
            ):
                logger.debug(
                    f"Key parameters changed for contestant {instance}, deleting previous flight orders and resetting gate times"
                )
                instance.predefined_gate_times = None
                previous_version.emailmaplink_set.all().delete()


@receiver(pre_delete, sender=Contestant)
def stop_any_calculators(sender, instance: Contestant, **kwargs):
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    ws.transmit_delete_contestant(instance)
    instance.request_calculator_termination()
    ScoreLogEntry.objects.filter(contestant=instance).delete()


@receiver(pre_save, sender=ContestTeam)
def validate_contest_team(sender, instance: ContestTeam, **kwargs):
    instance.clean()


@receiver(pre_save, sender=Crew)
def validate_crew(sender, instance: Crew, **kwargs):
    instance.validate()


@receiver(pre_save, sender=Club)
def validate_club(sender, instance: Club, **kwargs):
    instance.validate()


@receiver(pre_save, sender=Route)
def validate_route(sender, instance: Route, **kwargs):
    instance.clean()


@receiver(post_delete, sender=NavigationTask)
def remove_route_from_deleted_navigation_task(sender, instance: NavigationTask, **kwargs):
    instance.route.delete()
    if instance.scorecard:
        instance.scorecard.delete()


@receiver(pre_save, sender=NavigationTask)
def prevent_change_scorecard(sender, instance: NavigationTask, **kwargs):
    if instance.id is None:  # new object will be created
        pass  # write your code here
    else:
        previous = NavigationTask.objects.get(id=instance.id)

        if previous.original_scorecard != instance.original_scorecard:  # field will be updated
            raise ValidationError(
                f"Cannot change scorecard to {instance.original_scorecard.name}. You must create a new task."
            )


@receiver(pre_save, sender=Scorecard)
def update_contestant_initial_score(sender, instance: Scorecard, **kwargs):
    if instance.pk is not None:
        existing_initial_score = Scorecard.objects.get(pk=instance.pk).initial_score
        difference = instance.initial_score - existing_initial_score
        if difference != 0 and hasattr(instance, "navigation_task_override"):
            for contestant in instance.navigation_task_override.contestant_set.all():
                contestant.contestanttrack.increment_score(difference)


@receiver(post_save, sender=NavigationTask)
def initialise_navigation_task_dependencies(sender, instance: NavigationTask, created, **kwargs):
    if created:
        instance.assign_scorecard_from_original(force=False)
        instance.create_results_service_test()
        map_source = country_code_to_map_source(instance.contest.country)
        FlightOrderConfiguration.objects.get_or_create(navigation_task=instance, defaults={"map_source": map_source})


@receiver(pre_delete, sender=NavigationTask)
def clear_navigation_task_results_service_test(sender, instance: NavigationTask, **kwargs):
    if hasattr(instance, "tasktest") and instance.tasktest:
        task = instance.tasktest.task
        for team_test_score in instance.tasktest.teamtestscore_set.all():
            # Must be explicitly called for the signal to recalculate summary to be called.
            team_test_score.delete()
        instance.tasktest.delete()
        task.refresh_from_db()
        if task.tasktest_set.all().count() == 0:
            for task_summary in task.tasksummary_set.all():
                # Must be explicitly called for the signal to recalculate summary to be called.
                task_summary.delete()
            task.delete()


@receiver(post_save, sender=Contestant)
def create_tracker_in_traccar(sender, instance: Contestant, **kwargs):
    if (
        instance.tracking_service == TrackingService.TRACCAR
        and instance.tracker_device_id
        and len(instance.tracker_device_id) > 0
        and instance.tracking_device == TRACKING_DEVICE
    ):
        traccar = get_traccar_instance()
        traccar.get_or_create_device(instance.tracker_device_id, instance.tracker_device_id)


def generate_random_string(length) -> str:
    return "".join(choice(ascii_uppercase + ascii_lowercase + digits) for i in range(length))


@receiver(pre_save, sender=Person)
def register_personal_tracker(sender, instance: Person, **kwargs):
    instance.validate()
    if instance.pk is None:
        try:
            original = Person.objects.get(pk=instance.pk)
            original_tracking_id = original.app_tracking_id
            simulator_original_tracking_id = original.simulator_tracking_id
        except ObjectDoesNotExist:
            original_tracking_id = None
            simulator_original_tracking_id = None
        traccar = get_traccar_instance()
        app_random_string = "SHOULD_NOT_BE_HERE"
        simulator_random_string = "SHOULD_NOT_BE_HERE"
        existing = True
        while existing:
            app_random_string = generate_random_string(28)
            simulator_random_string = generate_random_string(28)
            logger.debug(f"Generated random string {app_random_string} for person {instance}")
            existing = Person.objects.filter(
                Q(app_tracking_id=app_random_string) | Q(simulator_tracking_id=simulator_random_string)
            ).exists()
        instance.app_tracking_id = app_random_string
        instance.simulator_tracking_id = simulator_random_string
        logger.debug(f"Assigned random string {instance.app_tracking_id} to person {instance}")
        device, created = traccar.get_or_create_device(str(instance), instance.app_tracking_id)
        logger.debug(f"Traccar device {device} was created: {created}")
        if created and original_tracking_id is not None and original_tracking_id != instance.app_tracking_id:
            original_device = traccar.get_device(original_tracking_id)
            if original_device is not None:
                logger.debug(f"Clearing original device {original_device}")
                traccar.delete_device(original_device["id"])
        device, created = traccar.get_or_create_device(str(instance) + " simulator", instance.simulator_tracking_id)
        logger.debug(f"Traccar device {device} was created: {created}")
        if (
            created
            and simulator_original_tracking_id is not None
            and simulator_original_tracking_id != instance.simulator_tracking_id
        ):
            original_device = traccar.get_device(simulator_original_tracking_id)
            if original_device is not None:
                logger.debug(f"Clearing original device {original_device}")
                traccar.delete_device(original_device["id"])
    else:
        original = Person.objects.get(pk=instance.pk)
        # Update traccar device names
        if str(original) != str(instance):
            traccar = get_traccar_instance()
            traccar.update_device_name(str(instance), instance.app_tracking_id)
            traccar.update_device_name(str(instance) + " simulator", instance.simulator_tracking_id)
    # Send welcome email if the person is validated, but previously was not
    previous_person = Person.objects.filter(pk=instance.pk).first()
    if instance.validated and ((previous_person and not previous_person.validated) or not previous_person):
        user = MyUser.objects.filter(email=instance.email).first()
        if user:
            user.send_welcome_email(instance)


@receiver(pre_delete, sender=Person)
def delete_personal_tracker(sender, instance: Person, **kwargs):
    if instance.app_tracking_id is not None:
        traccar = get_traccar_instance()
        original_device = traccar.get_device(instance.app_tracking_id)
        if original_device is not None:
            traccar.delete_device(original_device["id"])
    if instance.simulator_tracking_id is not None:
        traccar = get_traccar_instance()
        original_device = traccar.get_device(instance.simulator_tracking_id)
        if original_device is not None:
            traccar.delete_device(original_device["id"])


# Source - https://stackoverflow.com/a
# Posted by Dong
# Retrieved 2026-01-21, License - CC BY-SA 4.0

import secrets


def make_random_password(length=10, allowed_chars="abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"):
    return "".join(secrets.choice(allowed_chars) for i in range(length))


@receiver(post_save, sender=MyUser)
def create_random_password_for_user(sender, instance: MyUser, created: bool, **kwargs):
    if created:
        person = Person.objects.filter(email=instance.email).first()
        if person and person.validated:
            # This is a new user object for an already existing valid person. Send the welcome email.
            instance.send_welcome_email(person)
    
    # Do NOT set random passwords for users who are migrated to Firebase.
    # Firebase-migrated users have unusable passwords by design.
    # Also prevent infinite recursion if we do decide to save.
    if not instance.has_usable_password() and not getattr(instance, "_is_firebase_migrated", False):
        # Only set a random password if it's a truly new/empty local user 
        # that hasn't been explicitly marked as Firebase-migrated.
        # But wait, if they have an unusable password, we should probably 
        # only set a random one if they were just created and aren't migrated.
        if created:
            instance.set_password(make_random_password(length=20))
            instance.save(update_fields=["password"])


@receiver(signal=m2m_changed, sender=User.groups.through)
def adjust_group_notifications(instance, action, reverse, model, pk_set, using, *args, **kwargs):
    if model == Group and not reverse:
        logger.info("User %s deleted their relation to groups «%s»", instance.username, pk_set)
        if action == "post_remove":
            pass
        elif action == "post_add":
            logger.info(
                "User %s created a relation to groups «%s»", instance.username, ", ".join([str(i) for i in pk_set])
            )
            group = Group.objects.filter(pk__in=pk_set, name="ContestCreator").first()
            if group:
                person = Person.objects.filter(email=instance.email).first()
                if person:
                    instance.send_contest_creator_email(person)
    else:
        logger.info("Group %s is modifying its relation to users «%s»", instance, pk_set)


@receiver(post_save, sender=Scorecard)
def sync_scorecard_sorting_direction(sender, instance: Scorecard, **kwargs):
    if hasattr(instance, "navigation_task_override"):
        nt = instance.navigation_task_override
        if hasattr(nt, "tasktest"):
            nt.tasktest.sorting = instance.score_sorting_direction
            nt.tasktest.save(update_fields=["sorting"])
            nt.tasktest.task.summary_score_sorting_direction = instance.score_sorting_direction
            nt.tasktest.task.save(update_fields=["summary_score_sorting_direction"])


@receiver(post_save, sender=EditableRoute)
def calculate_editable_route_statistics(sender, instance: EditableRoute, **kwargs):
    EditableRoute.objects.filter(pk=instance.pk).update(
        number_of_waypoints=instance.calculate_number_of_waypoints(), route_length=instance.calculate_route_length()
    )
