import datetime

import dateutil
from django.db import transaction

from display.models import ContestTeam, Contestant
from display.services.contestant_task_compiler import ContestantTaskCompiler


TIME_FIELDS = ("takeoff_time", "tracker_start_time", "finished_by_time")
TEAM_DEFAULT_FIELDS = (
    "tracking_service",
    "tracking_device",
    "tracker_device_id",
    "air_speed",
)


def _normalize_datetime_fields(validated_data: dict) -> dict:
    normalized = dict(validated_data)
    for field_name in TIME_FIELDS:
        value = normalized.get(field_name)
        if isinstance(value, datetime.datetime) and value.tzinfo is not None:
            normalized[field_name] = value.astimezone(datetime.timezone.utc)
    return normalized


def _parse_gate_times(gate_times: dict | None) -> dict:
    gate_times = gate_times or {}
    return {key: dateutil.parser.parse(value) for key, value in gate_times.items()}


def _apply_contest_team_defaults(contest_team, validated_data: dict) -> dict:
    if contest_team is None:
        return validated_data
    normalized = dict(validated_data)
    for field_name in TEAM_DEFAULT_FIELDS:
        if field_name not in normalized or normalized[field_name] in (None, ""):
            normalized[field_name] = getattr(contest_team, field_name)
    return normalized


def _sync_contest_team(contestant: Contestant) -> None:
    ContestTeam.objects.update_or_create(
        defaults={
            "tracker_device_id": contestant.tracker_device_id,
            "tracking_service": contestant.tracking_service,
            "tracking_device": contestant.tracking_device,
            "air_speed": contestant.air_speed,
        },
        contest=contestant.navigation_task.contest,
        team=contestant.team,
    )


def _compile_contestant_configuration(contestant: Contestant, declaration_input) -> None:
    compiler = ContestantTaskCompiler(contestant)
    declaration_payload = compiler.build_declaration_payload_from_input(declaration_input)
    if declaration_payload or contestant.navigation_task.task_subtype:
        compiler.compile(declaration_payload=declaration_payload, force=True)


def create_contestant_with_related_state(navigation_task, validated_data: dict, gate_times: dict | None = None, declaration_input=None) -> Contestant:
    team = validated_data["team"]
    contest_team = ContestTeam.objects.filter(contest=navigation_task.contest, team=team).first()
    normalized_data = _apply_contest_team_defaults(contest_team, _normalize_datetime_fields(validated_data))
    normalized_data["navigation_task"] = navigation_task
    parsed_gate_times = _parse_gate_times(gate_times)

    # Ordering is deliberate: create contestant first, then apply gate-time
    # overrides, then normalize/compile declaration payload against the saved
    # contestant/task context, and finally sync ContestTeam defaults.
    with transaction.atomic():
        contestant = Contestant.objects.create(**normalized_data)
        if parsed_gate_times:
            contestant.gate_times = parsed_gate_times
            contestant.save(update_fields=["predefined_gate_times"])
        _compile_contestant_configuration(contestant, declaration_input)
        _sync_contest_team(contestant)
    return contestant


def update_contestant_with_related_state(instance: Contestant, validated_data: dict, gate_times: dict | None = None, declaration_input=None, partial: bool = False) -> Contestant:
    normalized_data = _normalize_datetime_fields(validated_data)
    if not partial:
        team = normalized_data["team"]
        contest_team = ContestTeam.objects.filter(contest=instance.navigation_task.contest, team=team).first()
        normalized_data = _apply_contest_team_defaults(contest_team, normalized_data)
    parsed_gate_times = _parse_gate_times(gate_times)

    # Ordering is deliberate here too: persist base contestant fields,
    # refresh/apply gate-time overrides, then recompile declaration-derived
    # contestant state, and only afterwards mirror the resolved tracking/speed
    # defaults back onto ContestTeam.
    with transaction.atomic():
        Contestant.objects.filter(pk=instance.pk).update(**normalized_data)
        instance.refresh_from_db()
        # Serializer/view callers pass gate_times=None when they intend to
        # clear predefined overrides, so updates always rewrite the persisted
        # gate-time payload instead of silently preserving stale values.
        instance.gate_times = parsed_gate_times
        instance.save()
        _compile_contestant_configuration(instance, declaration_input)
        _sync_contest_team(instance)
    return instance
