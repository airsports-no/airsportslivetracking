"""
The rules of series (display/models/series.py): who manages one, which contests can be legs of it, and the rule that
keeps a public series from showing a private contest. The standings are in display/services/series_standings.py.
"""

from django.db import transaction
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework.exceptions import PermissionDenied, ValidationError

from display.models import Contest, MyUser, Series, SeriesContest

SERIES_PERMISSIONS = ("view_series", "change_series", "delete_series")


def can_manage(user: MyUser, series: Series) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("display.change_series", series))


def can_view(user: MyUser, series: Series) -> bool:
    """A public series is for everybody, a private one for the people who manage it."""
    if series.is_public:
        return True
    return bool(user and user.is_authenticated and user.has_perm("display.view_series", series))


def visible_series(user: MyUser):
    """The series [user] may see: the public ones and those they manage."""
    if user is None or not user.is_authenticated:
        return Series.objects.filter(is_public=True)
    managed = get_objects_for_user(user, "display.view_series", klass=Series, accept_global_perms=False)
    return Series.objects.filter(is_public=True) | managed


def require_manager(user: MyUser, series: Series) -> None:
    if not can_manage(user, series):
        raise PermissionDenied("Only somebody who manages the series may do that.")


def create_series(user: MyUser, **fields) -> Series:
    """Anybody who may create contests may create a series; they manage it."""
    if not user.has_perm("display.add_contest"):
        raise PermissionDenied("Only an organiser may create a series.")
    series = Series(created_by=user, **fields)
    _validate(series)
    with transaction.atomic():
        series.save()
        for permission in SERIES_PERMISSIONS:
            assign_perm(f"display.{permission}", user, series)
    return series


def _validate(series: Series) -> None:
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        series.clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages)


def private_legs(series: Series):
    return series.contests.filter(is_public=False)


def update_series(series: Series, user: MyUser, **fields) -> Series:
    require_manager(user, series)
    for name, value in fields.items():
        setattr(series, name, value)
    _validate(series)
    if series.is_public and private_legs(series).exists():
        names = ", ".join(private_legs(series).values_list("name", flat=True))
        raise ValidationError(f"A public series can only contain public contests. Not public: {names}.")
    series.save()
    return series


def delete_series(series: Series, user: MyUser) -> None:
    if not user.has_perm("display.delete_series", series):
        raise PermissionDenied("Only somebody who may delete the series may do that.")
    series.delete()


def add_contest(
    series: Series, contest: Contest, user: MyUser, leg_number: int | None = None, weight: float = 1
) -> SeriesContest:
    """Make [contest] a leg of [series]. Needs the right to manage both."""
    require_manager(user, series)
    if not user.has_perm("display.change_contest", contest):
        raise PermissionDenied("You can only add contests you manage.")
    if series.is_public and not contest.is_public:
        raise ValidationError("A public series can only contain public contests. Make the contest public first.")
    if weight <= 0:
        raise ValidationError("The weight must be more than zero.")
    with transaction.atomic():
        if SeriesContest.objects.filter(series=series, contest=contest).exists():
            raise ValidationError("The contest is already in the series.")
        if leg_number is None:
            last = SeriesContest.objects.filter(series=series).order_by("-leg_number").first()
            leg_number = (last.leg_number + 1) if last else 1
        return SeriesContest.objects.create(
            series=series, contest=contest, leg_number=leg_number, weight=weight, added_by=user
        )


def update_leg(link: SeriesContest, user: MyUser, leg_number: int | None = None, weight: float | None = None):
    require_manager(user, link.series)
    if weight is not None:
        if weight <= 0:
            raise ValidationError("The weight must be more than zero.")
        link.weight = weight
    if leg_number is not None:
        link.leg_number = leg_number
    link.save(update_fields=["leg_number", "weight"])
    return link


def remove_contest(link: SeriesContest, user: MyUser) -> None:
    """The people who manage the series, and those who manage the contest, can take a contest out of a series."""
    if not (can_manage(user, link.series) or user.has_perm("display.change_contest", link.contest)):
        raise PermissionDenied("Only somebody who manages the series or the contest may take the contest out.")
    link.delete()


def addable_contests(series: Series, user: MyUser):
    """The contests [user] could add: those they manage that are not in the series, public ones only for a public series."""
    managed = get_objects_for_user(
        user, "display.change_contest", klass=Contest, accept_global_perms=False, with_superuser=False
    ).exclude(series=series)
    if series.is_public:
        managed = managed.filter(is_public=True)
    return managed.order_by("-start_time")


def public_series_of(contest: Contest):
    return Series.objects.filter(is_public=True, contests=contest)


def assert_contest_can_be_private(contest: Contest) -> None:
    """A contest in a public series stays public: otherwise the series would show it to everybody."""
    series = list(public_series_of(contest).values_list("name", flat=True))
    if series:
        raise ValidationError(
            f"The contest is a leg of the public series {', '.join(series)}. Take it out of the series or make the series private first."
        )
