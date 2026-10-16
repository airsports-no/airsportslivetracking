import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import ProtectedError
from django.test import TestCase
from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm
from rest_framework.test import APIClient

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestTeam,
    ContestTokenAssignment,
    Crew,
    NavigationTask,
    Person,
    Route,
    Team,
    TokenType,
    UserTokenGrant,
)
from display.utilities.tracking_definitions import TRACKING_PILOT
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock

URL = "/api/v1/userprofile/delete_account/"


def waypoint(name, latitude, longitude, bearing_next=-1):
    w = Waypoint(name)
    w.latitude = latitude
    w.longitude = longitude
    w.gate_line = []
    w.bearing_next = bearing_next
    return w


class TestAccountDeletionApi(TestCase):
    def setUp(self):
        for target in ("display.signals.get_traccar_instance",):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        firebase = patch("display.services.account_deletion._delete_firebase_user", return_value=True)
        self.firebase_delete = firebase.start()
        self.addCleanup(firebase.stop)
        email = patch("display.models.MyUser.send_deletion_email")
        self.deletion_email = email.start()
        self.addCleanup(email.stop)

        self.User = get_user_model()
        self.user = self.User.objects.create(
            username="pilot", email="pilot@example.com", first_name="Pi", last_name="Lot"
        )
        self.person = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com", validated=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_deletes_login_profile_and_firebase_account(self):
        response = self.client.delete(URL, {"email": "Pilot@Example.com"}, format="json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.User.objects.filter(email="pilot@example.com").exists())
        self.assertFalse(Person.objects.filter(email="pilot@example.com").exists())
        self.firebase_delete.assert_called_once_with("pilot@example.com")
        self.deletion_email.assert_called_once()

    def test_requires_matching_email_confirmation(self):
        for body in ({}, {"email": "someone@else.com"}):
            response = self.client.delete(URL, body, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertTrue(self.User.objects.filter(email="pilot@example.com").exists())
        self.assertTrue(Person.objects.filter(email="pilot@example.com").exists())
        self.firebase_delete.assert_not_called()

    def test_person_referenced_by_a_team_is_anonymized_not_deleted(self):
        with patch("display.services.account_deletion.Person.delete", side_effect=ProtectedError("protected", set())):
            response = self.client.delete(URL, {"email": "pilot@example.com"}, format="json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.User.objects.filter(email="pilot@example.com").exists())
        self.person.refresh_from_db()
        self.assertEqual((self.person.first_name, self.person.last_name), ("Unknown", "Unknown"))
        self.assertEqual(self.person.email, f"internal_{self.person.pk}@airsports.no")
        self.assertFalse(self.person.is_public)

    def test_staff_and_superusers_cannot_self_delete(self):
        for flag in ("is_staff", "is_superuser"):
            User = self.User
            User.objects.filter(pk=self.user.pk).update(is_staff=False, is_superuser=False)
            User.objects.filter(pk=self.user.pk).update(**{flag: True})
            self.client.force_authenticate(User.objects.get(pk=self.user.pk))
            response = self.client.delete(URL, {"email": "pilot@example.com"}, format="json")

            self.assertEqual(response.status_code, 409, flag)
            self.assertEqual(
                response.json()["detail"],
                "Staff and administrator accounts must be deleted by support. Contact support@airsports.no.",
            )
            self.assertTrue(User.objects.filter(email="pilot@example.com").exists())
            self.assertTrue(Person.objects.filter(email="pilot@example.com").exists())
        self.firebase_delete.assert_not_called()

    def test_a_failing_firebase_deletion_changes_nothing(self):
        self.firebase_delete.return_value = False
        response = self.client.delete(URL, {"email": "pilot@example.com"}, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertIn("nothing was changed", response.json()["detail"])
        self.assertTrue(self.User.objects.filter(email="pilot@example.com").exists())
        self.assertTrue(Person.objects.filter(email="pilot@example.com").exists())
        self.deletion_email.assert_not_called()

    def test_requires_authentication(self):
        response = APIClient().delete(URL, {"email": "pilot@example.com"}, format="json")
        self.assertIn(response.status_code, (401, 403))
        self.assertTrue(self.User.objects.filter(email="pilot@example.com").exists())


class TestOrganizerAccountDeletion(TestCase):
    """Organizers delete their account like everybody else; their contests and all results stay."""

    def setUp(self):
        for target in ("display.signals.get_traccar_instance", "display.models.contestant.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        firebase = patch("display.services.account_deletion._delete_firebase_user", return_value=True)
        self.firebase_delete = firebase.start()
        self.addCleanup(firebase.stop)
        email = patch("display.models.MyUser.send_deletion_email")
        self.deletion_email = email.start()
        self.addCleanup(email.stop)
        support = patch("display.services.account_deletion.send_mail")
        self.support_mail = support.start()
        self.addCleanup(support.stop)

        self.User = get_user_model()
        self.organizer = self.User.objects.create(
            username="organizer", email="organizer@example.com", first_name="Or", last_name="Ganizer"
        )
        self.person = Person.objects.create(
            first_name="Or", last_name="Ganizer", email="organizer@example.com", validated=True
        )
        group, _ = Group.objects.get_or_create(name="ContestCreator")
        group.permissions.add(Permission.objects.get(codename="add_contest", content_type__app_label="display"))
        self.organizer.groups.add(group)
        self.organizer = self.User.objects.get(pk=self.organizer.pk)
        self.assertTrue(
            self.organizer.has_perm("display.add_contest"), "the premise: the group gives the global permission"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.organizer)
        self.now = datetime.datetime.now(datetime.timezone.utc)

    def make_contest(self, name, running=False, managers=()):
        start = self.now - datetime.timedelta(hours=1) if running else self.now + datetime.timedelta(days=30)
        contest = Contest.objects.create(
            name=name,
            start_time=start,
            finish_time=start + datetime.timedelta(days=2),
            is_public=True,
            created_by=self.organizer,
        )
        for user in (self.organizer, *managers):
            for permission in ("view_contest", "change_contest", "add_contest", "delete_contest"):
                assign_perm(permission, user, contest)
        return contest

    def add_other_pilots_flight(self, contest):
        """A task with a flight of another pilot: results that depend on the contest."""
        route = Route.objects.create(
            name="Route", waypoints=[waypoint("SP", 59.97, 11.20, bearing_next=90.0), waypoint("TP1", 59.97, 11.40)]
        )
        task = NavigationTask.create(
            name="Task",
            original_scorecard=get_default_scorecard(),
            start_time=self.now - datetime.timedelta(hours=2),
            finish_time=self.now + datetime.timedelta(days=2),
            route=route,
            contest=contest,
            is_public=True,
        )
        pilot = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot), aeroplane=Aeroplane.objects.create(registration="LN-OTH")
        )
        ContestTeam.objects.create(contest=contest, team=team, air_speed=70)
        flight = Contestant.objects.create(
            team=team,
            navigation_task=task,
            tracking_device=TRACKING_PILOT,
            contestant_number=1,
            tracker_start_time=self.now - datetime.timedelta(minutes=30),
            takeoff_time=self.now + datetime.timedelta(minutes=10),
            finished_by_time=self.now + datetime.timedelta(hours=2),
        )
        return task, flight

    def delete(self):
        return self.client.delete(URL, {"email": "organizer@example.com"}, format="json")

    def test_an_organizer_without_contests_is_deleted_like_a_pilot(self):
        response = self.delete()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(b"", response.content)
        self.assertFalse(self.User.objects.filter(email="organizer@example.com").exists())
        self.assertFalse(Person.objects.filter(email="organizer@example.com").exists())
        self.firebase_delete.assert_called_once_with("organizer@example.com")
        self.deletion_email.assert_called_once()
        self.support_mail.assert_not_called()

    def test_contests_and_results_survive_and_the_personal_data_and_rights_are_gone(self):
        co_manager = self.User.objects.create(username="co", email="co@example.com")
        contest = self.make_contest("Cup", managers=(co_manager,))
        task, flight = self.add_other_pilots_flight(contest)
        owner_id = self.organizer.pk

        response = self.delete()

        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.User.objects.filter(pk=owner_id).exists())
        self.assertFalse(Person.objects.filter(email="organizer@example.com").exists())
        contest.refresh_from_db()
        self.assertIsNone(contest.created_by, "nobody is named as the creator any more")
        self.assertTrue(NavigationTask.objects.filter(pk=task.pk).exists())
        self.assertTrue(Contestant.objects.filter(pk=flight.pk).exists(), "the other pilots' results stay")
        self.assertTrue(ContestTeam.objects.filter(contest=contest).exists())
        self.assertFalse(
            UserObjectPermission.objects.filter(user_id=owner_id).exists(), "the rights go with the account"
        )
        self.assertTrue(co_manager.has_perm("display.change_contest", contest), "the others keep theirs")
        self.support_mail.assert_not_called()  # somebody can still manage the contest

    def test_support_is_told_about_contests_nobody_else_can_manage(self):
        alone = self.make_contest("Alone")
        shared = self.make_contest(
            "Shared", managers=(self.User.objects.create(username="co", email="co@example.com"),)
        )

        response = self.delete()

        self.assertEqual(response.status_code, 204)
        self.support_mail.assert_called_once()
        body = self.support_mail.call_args[0][1]
        self.assertIn(f"contest {alone.pk}: Alone", body)
        self.assertNotIn("Shared", body)
        self.assertNotIn("organizer@example.com", body, "no personal data in the notice")
        self.assertEqual(["support@airsports.no"], self.support_mail.call_args.kwargs["recipient_list"])
        self.assertTrue(Contest.objects.filter(pk=alone.pk).exists() and Contest.objects.filter(pk=shared.pk).exists())

    def test_a_contest_that_is_running_with_other_crews_still_goes_through_and_is_flagged(self):
        contest = self.make_contest("Running", running=True)
        _, flight = self.add_other_pilots_flight(contest)

        response = self.delete()

        self.assertEqual(response.status_code, 204)
        self.assertTrue(Contestant.objects.filter(pk=flight.pk).exists())
        self.assertIn("RUNNING NOW", self.support_mail.call_args[0][1])

    def test_a_team_member_organizer_is_anonymized_and_the_contest_is_kept(self):
        contest = self.make_contest("Own flights")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=self.person), aeroplane=Aeroplane.objects.create(registration="LN-OWN")
        )
        ContestTeam.objects.create(contest=contest, team=team, air_speed=70)

        response = self.delete()

        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.User.objects.filter(email="organizer@example.com").exists())
        self.person.refresh_from_db()
        self.assertEqual((self.person.first_name, self.person.last_name), ("Unknown", "Unknown"))
        self.assertEqual(self.person.email, f"internal_{self.person.pk}@airsports.no")
        self.assertTrue(Contest.objects.filter(pk=contest.pk).exists())

    def test_a_token_that_a_contest_runs_on_keeps_an_anonymous_inactive_login(self):
        contest = self.make_contest("Paid")
        token_type = TokenType.objects.create(name="Small token", contestant_limit=10)
        used = UserTokenGrant.objects.create(
            user=self.organizer, token_type=token_type, quantity_total=2, quantity_consumed=1
        )
        unused = UserTokenGrant.objects.create(user=self.organizer, token_type=token_type, quantity_total=3)
        ContestTokenAssignment.objects.create(contest=contest, token_grant=used, token_type=token_type)
        owner_id = self.organizer.pk

        response = self.delete()

        self.assertEqual(response.status_code, 204)
        kept = self.User.objects.get(pk=owner_id)
        self.assertEqual(f"deleted_{owner_id}@airsports.no", kept.email)
        self.assertEqual(("", ""), (kept.first_name, kept.last_name))
        self.assertFalse(kept.is_active)
        self.assertFalse(kept.has_usable_password())
        self.assertFalse(kept.groups.exists())
        self.assertFalse(kept.has_perm("display.add_contest"))
        self.assertFalse(UserObjectPermission.objects.filter(user_id=owner_id).exists())
        self.assertTrue(UserTokenGrant.objects.filter(pk=used.pk).exists(), "the contest keeps running on its token")
        self.assertFalse(UserTokenGrant.objects.filter(pk=unused.pk).exists())
        self.assertTrue(ContestTokenAssignment.objects.filter(contest=contest).exists())
        self.assertFalse(Person.objects.filter(email="organizer@example.com").exists())
        self.assertFalse(self.User.objects.filter(email="organizer@example.com").exists(), "the address is free again")
        self.deletion_email.assert_called_once()

    def test_a_failure_halfway_leaves_everything_as_it_was(self):
        contest = self.make_contest("Alone")
        self.firebase_delete.return_value = False

        response = self.delete()

        self.assertEqual(response.status_code, 503)
        self.assertTrue(self.User.objects.filter(email="organizer@example.com").exists())
        self.assertTrue(Person.objects.filter(email="organizer@example.com").exists())
        contest.refresh_from_db()
        self.assertEqual(self.organizer.pk, contest.created_by_id)
        self.assertTrue(self.organizer.has_perm("display.change_contest", contest))
        self.support_mail.assert_not_called()
        self.deletion_email.assert_not_called()

    def test_membership_of_the_organizer_group_alone_never_blocks(self):
        from display.services.account_deletion import blocked_reason

        self.assertIsNone(blocked_reason(self.organizer))
