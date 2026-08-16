import datetime

from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from django.test import TestCase, override_settings

from display.models import (
    Contest,
    Club,
    AccessGrant,
    TokenType,
    UserTokenGrant,
    ContestTokenAssignment,
    ClubManagerMembership,
    UserEntitlementGrant,
)
from display.services.access_resolver import resolve_contest_access
from display.services.capacity_enforcement import assert_can_add_navigation_task
from display.utilities.cima_task_type_definitions import CIRCLE, CONTRACT_NAVIGATION_TIME_CONTROLS, TURNPOINT_HUNT
from display.utilities.navigation_task_type_definitions import PRECISION
from display.utilities.task_type_group_definitions import CIMA_TASK_TYPE_GROUP, LEGACY_TASK_TYPE_GROUP


@override_settings(
    DEFAULT_FREE_CONTESTANT_LIMIT=None,
    DEFAULT_FREE_TASK_TYPE_GROUPS=[LEGACY_TASK_TYPE_GROUP],
    ACCESS_ENFORCEMENT_MODE="enforce",
)
class TestTaskTypeGroupAccess(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="task-groups@example.com")
        self.club = Club.objects.create(name="Task Group Club")
        self.contest = Contest.objects.create(
            name="Task Group Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 9, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 9, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
            organizing_club=self.club,
        )

    def test_free_defaults_allow_legacy_tasks_but_block_cima_tasks(self):
        legacy_resolution = assert_can_add_navigation_task(self.contest, task_type=PRECISION, task_subtype="")
        self.assertIn(LEGACY_TASK_TYPE_GROUP, legacy_resolution.allowed_task_type_groups)
        self.assertNotIn(CIMA_TASK_TYPE_GROUP, legacy_resolution.allowed_task_type_groups)

        with self.assertRaises(ValidationError):
            assert_can_add_navigation_task(
                self.contest,
                task_type=PRECISION,
                task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            )

    def test_token_assignment_can_explicitly_enable_cima_tasks(self):
        token_type = TokenType.objects.create(
            name="CIMA token",
            contestant_limit=10,
            task_type_groups=[CIMA_TASK_TYPE_GROUP],
        )
        token_grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        ContestTokenAssignment.objects.create(
            contest=self.contest,
            token_grant=token_grant,
            token_type=token_type,
        )

        resolution = resolve_contest_access(self.contest)
        self.assertIn(LEGACY_TASK_TYPE_GROUP, resolution.allowed_task_type_groups)
        self.assertIn(CIMA_TASK_TYPE_GROUP, resolution.allowed_task_type_groups)

        allowed = assert_can_add_navigation_task(
            self.contest,
            task_type=PRECISION,
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
        )
        self.assertIn(CIMA_TASK_TYPE_GROUP, allowed.allowed_task_type_groups)

    @override_settings(GATE_CIMA_TASK_VISIBILITY=True)
    def test_beta_club_manager_can_add_cima_task_to_own_ungranted_contest(self):
        # The contest's own organizing club has no grant, so contest-resolved
        # access alone would reject a CIMA task...
        with self.assertRaises(ValidationError):
            assert_can_add_navigation_task(
                self.contest,
                task_type=PRECISION,
                task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            )

        # ...but a user who manages a *different* club with a CIMA access
        # grant (e.g. a beta-test club) should still be able to add CIMA
        # tasks to their own contest, since visibility of a task-type group
        # should not require organizing every contest under the beta club.
        beta_club = Club.objects.create(name="Beta Testers Club")
        AccessGrant.objects.create(
            club=beta_club,
            status=AccessGrant.ACTIVE,
            contestant_limit=None,
            task_type_groups=[CIMA_TASK_TYPE_GROUP],
        )
        ClubManagerMembership.objects.create(club=beta_club, user=self.user)

        allowed = assert_can_add_navigation_task(
            self.contest,
            task_type=PRECISION,
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            user=self.user,
        )
        self.assertIn(CIMA_TASK_TYPE_GROUP, allowed.allowed_task_type_groups)

    def test_club_pass_can_explicitly_enable_cima_tasks(self):
        AccessGrant.objects.create(
            club=self.club,
            status=AccessGrant.ACTIVE,
            contestant_limit=None,
            task_type_groups=[CIMA_TASK_TYPE_GROUP],
        )

        resolution = resolve_contest_access(self.contest)
        self.assertIn(LEGACY_TASK_TYPE_GROUP, resolution.allowed_task_type_groups)
        self.assertIn(CIMA_TASK_TYPE_GROUP, resolution.allowed_task_type_groups)

        allowed = assert_can_add_navigation_task(
            self.contest,
            task_type=PRECISION,
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
        )
        self.assertIn(CIMA_TASK_TYPE_GROUP, allowed.allowed_task_type_groups)

    def test_fine_grained_entitlement_grant_allows_only_the_granted_subtype(self):
        UserEntitlementGrant.objects.create(
            user=self.user,
            kind=UserEntitlementGrant.KIND_TASK_TYPE_GROUP,
            value="cima:circle",
        )

        # Granted subtype succeeds.
        allowed = assert_can_add_navigation_task(
            self.contest,
            task_type=PRECISION,
            task_subtype=CIRCLE,
            user=self.user,
        )
        self.assertIn("cima:circle", allowed.allowed_task_type_groups)

        # A different CIMA subtype is not covered by the fine-grained grant.
        with self.assertRaises(ValidationError):
            assert_can_add_navigation_task(
                self.contest,
                task_type=PRECISION,
                task_subtype=TURNPOINT_HUNT,
                user=self.user,
            )
