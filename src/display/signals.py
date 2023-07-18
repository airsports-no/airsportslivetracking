import logging
from functools import wraps
from random import choice
from string import ascii_uppercase, ascii_lowercase, digits

from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.db.models.signals import post_save, post_delete, pre_delete, pre_save, m2m_changed
from django.dispatch import receiver

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
    NavigationTask,
    FlightOrderConfiguration,
    TRACCAR,
    TRACKING_DEVICE,
    Person,
    MyUser,
    EditableRoute,
    Contest,
)
from display.utilities.country_code_utilities import get_country_code_from_location
from display.utilities.traccar_factory import get_traccar_instance

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=TeamTestScore)
@receiver(post_delete, sender=TeamTestScore)
def auto_summarise_tests(sender, instance: TeamTestScore, **kwargs):
    try:
        if instance.task_test.task.autosum_scores:
            task_summary, _ = TaskSummary.objects.get_or_create(
                task=instance.task_test.task,
                team=instance.team,
                defaults={"points": instance.points},
            )
            task_summary.update_sum()
    except ObjectDoesNotExist:
        pass


@receiver(post_save, sender=TaskSummary)
@receiver(post_delete, sender=TaskSummary)
def auto_summarise_tasks(sender, instance: TaskSummary, **kwargs):
    try:
        if instance.task.contest.autosum_scores:
            contest_summary, _ = ContestSummary.objects.get_or_create(
                contest=instance.task.contest,
                team=instance.team,
                defaults={"points": instance.points},
            )
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
    from websocket_channels import WebsocketFacade

    try:
        ws = WebsocketFacade()
        ws.transmit_contest_results(None, instance.task_test.task.contest)
    except ObjectDoesNotExist:
        pass


@receiver(post_save, sender=TaskSummary)
@receiver(post_delete, sender=TaskSummary)
def post_task_summary_change(sender, instance: TaskSummary, **kwargs):
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    try:
        ws.transmit_contest_results(None, instance.task.contest)
    except ObjectDoesNotExist:
        pass


@receiver(post_save, sender=ContestSummary)
@receiver(post_delete, sender=ContestSummary)
def push_contest_summary_change(sender, instance: ContestSummary, **kwargs):
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    ws.transmit_contest_results(None, instance.contest)


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
            instance.save()


@receiver(post_save, sender=TaskTest)
@receiver(post_delete, sender=TaskTest)
def push_test_change(sender, instance: TaskTest, **kwargs):
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    try:
        ws.transmit_tests(instance.task.contest)
    except ObjectDoesNotExist:
        pass


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
    ContestantTrack.objects.get_or_create(contestant=instance)
    from websocket_channels import WebsocketFacade

    ws = WebsocketFacade()
    ws.transmit_contestant(instance)


@receiver(pre_save, sender=Contestant)
def validate_contestant(sender, instance: Contestant, **kwargs):
    instance.clean()


@receiver(pre_save, sender=Contestant)
def delete_flight_order_if_changed(sender, instance: Contestant, **kwargs):
    if instance.pk:
        if previous_version := Contestant.objects.filter(pk=instance.pk).first():
            if (
                previous_version.starting_point_time != instance.starting_point_time
                or previous_version.wind_speed != instance.wind_speed
                or previous_version.wind_direction != instance.wind_direction
                or previous_version.air_speed != instance.air_speed
            ):
                logger.debug(f"Key parameters changed for contestant {instance}, deleting previous flight orders")
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


@receiver(pre_save, sender=Contest)
def set_contest_location(sender, instance: Contest, **kwargs):
    instance.country = get_country_code_from_location(instance.latitude, instance.longitude)


@receiver(post_save, sender=NavigationTask)
def initialise_navigation_task_dependencies(sender, instance: NavigationTask, created, **kwargs):
    if created:
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
        instance.tracking_service == TRACCAR
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
    if previous_person and not previous_person.validated and instance.validated:
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


@receiver(post_save, sender=MyUser)
def create_random_password_for_user(sender, instance: MyUser, created: bool, **kwargs):
    if created:
        person = Person.objects.filter(email=instance.email).first()
        if person and person.validated:
            # This is a new user object for an already existing valid person. Send the welcome email.
            instance.send_welcome_email(person)
    if not instance.has_usable_password():
        instance.set_password(MyUser.objects.make_random_password(length=20))
        instance.save()


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


@receiver(post_save, sender=EditableRoute)
def calculate_editable_route_statistics(sender, instance: EditableRoute, **kwargs):
    EditableRoute.objects.filter(pk=instance.pk).update(
        number_of_waypoints=instance.calculate_number_of_waypoints(), route_length=instance.calculate_route_length()
    )
