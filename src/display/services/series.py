"""
The rules of series (display/models/series.py): who manages one, which contests can be legs of it, and the rule that
keeps a public series from showing a private contest. The standings are in display/services/series_standings.py.
"""

from django.db import transaction
from django.utils import timezone
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework.exceptions import PermissionDenied, ValidationError

from display.models import Contest, MyUser, Series, SeriesContest, SeriesContestRequest
from display.services.contest_visibility import can_view_contest

SERIES_PERMISSIONS = ("view_series", "change_series", "delete_series")


def can_manage(user: MyUser, series: Series) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("display.change_series", series))


def can_view(user: MyUser, series: Series) -> bool:
    """A public series is for everybody, a private one for the people who have been given access to it."""
    if series.is_public:
        return True
    return bool(user and user.is_authenticated and user.has_perm("display.view_series", series))


def visible_series(user: MyUser):
    """The series [user] may see: the public ones and those they have been given access to."""
    if user is None or not user.is_authenticated:
        return Series.objects.filter(is_public=True)
    managed = get_objects_for_user(user, "display.view_series", klass=Series, accept_global_perms=False)
    return Series.objects.filter(is_public=True) | managed


def series_of_managed_contests(user: MyUser):
    """The series that have a contest [user] manages as a leg, also private ones: so a leg can always leave."""
    managed_contests = get_objects_for_user(
        user, "display.change_contest", klass=Contest, accept_global_perms=False, with_superuser=False
    )
    return Series.objects.filter(contests__in=managed_contests.values("pk"))


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


def can_manage_contest(user: MyUser, contest: Contest) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("display.change_contest", contest))


def _check_can_join(series: Series, contest: Contest) -> None:
    if SeriesContest.objects.filter(series=series, contest=contest).exists():
        raise ValidationError("The contest is already in the series.")
    if series.is_public and not contest.is_public:
        raise ValidationError("A public series can only contain public contests. Make the contest public first.")


def request_enrolment(series: Series, contest: Contest, user: MyUser):
    """
    Get [contest] into [series]. Somebody who manages both adds it at once (returns the leg). Otherwise the managers of
    the other side get a request to answer (returns the request): the managers of the series invite a contest they can
    see, the managers of a contest ask to join a series they can see.
    """
    manages_series = can_manage(user, series)
    manages_contest = can_manage_contest(user, contest)
    if manages_series and manages_contest:
        return add_contest(series, contest, user)
    if manages_series:
        if not can_view_contest(user, contest):
            raise PermissionDenied("You can only invite contests you can see.")
        side = SeriesContestRequest.FROM_SERIES
    elif manages_contest:
        if not can_view(user, series):
            raise PermissionDenied("You can only ask to join series you can see.")
        side = SeriesContestRequest.FROM_CONTEST
    else:
        raise PermissionDenied("You need to manage the series or the contest.")
    with transaction.atomic():
        # Locking the series makes the check for an earlier request safe against a double click
        Series.objects.select_for_update().get(pk=series.pk)
        _check_can_join(series, contest)
        if SeriesContestRequest.objects.filter(
            series=series, contest=contest, status=SeriesContestRequest.PENDING
        ).exists():
            raise ValidationError("There is already a request for this contest and series waiting for an answer.")
        return SeriesContestRequest.objects.create(series=series, contest=contest, from_side=side, requested_by=user)


def _managers_of_the_other_side(request: SeriesContestRequest, user: MyUser) -> bool:
    if request.from_side == SeriesContestRequest.FROM_SERIES:
        return can_manage_contest(user, request.contest)
    return can_manage(user, request.series)


def _managers_of_the_asking_side(request: SeriesContestRequest, user: MyUser) -> bool:
    if request.from_side == SeriesContestRequest.FROM_SERIES:
        return can_manage(user, request.series)
    return can_manage_contest(user, request.contest)


def can_answer(request: SeriesContestRequest, user: MyUser) -> bool:
    return request.status == SeriesContestRequest.PENDING and _managers_of_the_other_side(request, user)


def can_cancel(request: SeriesContestRequest, user: MyUser) -> bool:
    return request.status == SeriesContestRequest.PENDING and _managers_of_the_asking_side(request, user)


def _close(request: SeriesContestRequest, status: str, user: MyUser) -> None:
    request.status = status
    request.responded_by = user
    request.responded_at = timezone.now()
    request.save(update_fields=["status", "responded_by", "responded_at"])


def accept_request(request: SeriesContestRequest, user: MyUser) -> SeriesContest:
    """The managers of the other side say yes: the contest becomes a leg."""
    with transaction.atomic():
        request = _locked(request)
        if not can_answer(request, user):
            raise PermissionDenied("This request is not open for you to answer.")
        _check_can_join(request.series, request.contest)
        last = SeriesContest.objects.filter(series=request.series).order_by("-leg_number").first()
        link = SeriesContest.objects.create(
            series=request.series,
            contest=request.contest,
            leg_number=(last.leg_number + 1) if last else 1,
            added_by=request.requested_by,
        )
        _close(request, SeriesContestRequest.ACCEPTED, user)
    return link


def _locked(request: SeriesContestRequest) -> SeriesContestRequest:
    """The request as it is now, locked: a request accepted at the same moment must not be declined or cancelled after."""
    return SeriesContestRequest.objects.select_for_update().select_related("series", "contest").get(pk=request.pk)


def decline_request(request: SeriesContestRequest, user: MyUser) -> None:
    with transaction.atomic():
        request = _locked(request)
        if not can_answer(request, user):
            raise PermissionDenied("This request is not open for you to answer.")
        _close(request, SeriesContestRequest.DECLINED, user)


def cancel_request(request: SeriesContestRequest, user: MyUser) -> None:
    with transaction.atomic():
        request = _locked(request)
        if not can_cancel(request, user):
            raise PermissionDenied("Only the side that asked can take the request back.")
        _close(request, SeriesContestRequest.CANCELLED, user)


def requests_for(user: MyUser):
    """The open requests that involve [user]: those they can answer, and those they or their co-managers made."""
    if user is None or not user.is_authenticated:
        return SeriesContestRequest.objects.none()
    managed_series = get_objects_for_user(
        user, "display.change_series", klass=Series, accept_global_perms=False, with_superuser=False
    )
    managed_contests = get_objects_for_user(
        user, "display.change_contest", klass=Contest, accept_global_perms=False, with_superuser=False
    )
    pending = SeriesContestRequest.objects.filter(status=SeriesContestRequest.PENDING)
    return (
        (
            pending.filter(series__in=managed_series.values("pk"))
            | pending.filter(contest__in=managed_contests.values("pk"))
        )
        .select_related("series", "contest", "requested_by")
        .distinct()
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
