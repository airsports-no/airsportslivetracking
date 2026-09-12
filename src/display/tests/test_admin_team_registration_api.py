"""
Coverage for ContestViewSet.register_team/import_teams and AdminTeamRegistrationSerialiser -
the React admin team-registration flow's backend, replacing RegisterTeamWizard (slice 4 of the
wizard->SPA migration plan). Pins down the "real bugs fixed by this migration" list:
- non-mutation of a reused aeroplane/club's fields (RegisterTeamWizard always overwrote them)
- a bad person id returns 400, not an unhandled 500 (member2 used to use Person.objects.get())
- the wizard never called assert_can_register_team at all
- no duplicate/cross-team/self-as-copilot checks existed
- no row locking / atomicity existed
"""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from display.models import Aeroplane, Club, Contest, ContestTeam, Person, Team


def _make_contest(owner, name="Admin registration contest"):
    contest = Contest.objects.create(
        name=name,
        time_zone="Europe/Oslo",
        start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
        finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
        location="60.0,11.0",
    )
    contest.initialise(owner)
    return contest


class TestAdminTeamRegistrationApi(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="admin-reg-owner@example.com", password="secret")
        self.owner.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.contest = _make_contest(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = f"/api/v1/contests/{self.contest.pk}/register_team/"

    def _payload(self, **overrides):
        payload = {
            "pilot": {"mode": "create", "first_name": "New", "last_name": "Pilot", "email": "new-pilot@example.com"},
            "copilot": {"mode": "skip"},
            "aeroplane": {"registration": "LN-NEW", "type": "Cessna 172", "colour": "White"},
            "club": {"name": "New Flying Club", "country": "NO"},
            "air_speed": 90,
            "tracking_service": "traccar",
            "tracking_device": "pilot_app",
        }
        payload.update(overrides)
        return payload

    def test_registers_new_team(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertTrue(Person.objects.filter(email="new-pilot@example.com", validated=True).exists())
        self.assertTrue(ContestTeam.objects.filter(contest=self.contest).exists())

    def test_reusing_existing_aeroplane_and_club_does_not_mutate_them(self):
        existing_aeroplane = Aeroplane.objects.create(registration="LN-ABC", type="Cessna", colour="Red")
        existing_club = Club.objects.create(name="Existing Club", country="SE")

        response = self.client.post(
            self.url,
            self._payload(
                aeroplane={"registration": "LN-ABC", "type": "Piper", "colour": "Blue"},
                club={"name": "Existing Club", "country": "NO"},
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        existing_aeroplane.refresh_from_db()
        existing_club.refresh_from_db()
        self.assertEqual(existing_aeroplane.type, "Cessna")
        self.assertEqual(existing_aeroplane.colour, "Red")
        self.assertEqual(existing_club.country, "SE")

    def test_bad_existing_person_id_returns_400_not_500(self):
        response = self.client.post(
            self.url,
            self._payload(pilot={"mode": "existing", "person": 999999}),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_pilot_and_copilot_cannot_be_the_same_person(self):
        person = Person.objects.create(first_name="Same", last_name="Person", email="same@example.com")
        response = self.client.post(
            self.url,
            self._payload(
                pilot={"mode": "existing", "person": person.pk},
                copilot={"mode": "existing", "person": person.pk},
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_duplicate_team_registration_is_rejected(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        team = Team.objects.get(aeroplane__registration="LN-NEW")
        response = self.client.post(
            self.url,
            self._payload(pilot={"mode": "existing", "person": team.crew.member1.pk}),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(ContestTeam.objects.filter(contest=self.contest, team=team).count(), 1)

    def test_pilot_already_registered_in_a_different_team_is_rejected(self):
        self.client.post(self.url, self._payload(), format="json")
        pilot = Person.objects.get(email="new-pilot@example.com")

        response = self.client.post(
            self.url,
            self._payload(
                pilot={"mode": "existing", "person": pilot.pk},
                aeroplane={"registration": "LN-OTHER", "type": "Piper", "colour": "Blue"},
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_non_editor_forbidden(self):
        # ContestViewSet.get_queryset() scopes every action (not just list/retrieve) to contests
        # the user can view - a non-editor, non-viewer user 404s before ContestModificationPermissions
        # even runs, same as every other admin action on this ViewSet (e.g. update_contest_summary).
        other_user = get_user_model().objects.create_user(email="not-an-editor@example.com", password="secret")
        client = APIClient()
        client.force_authenticate(other_user)
        response = client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    def test_edit_replaces_the_registered_team(self):
        create_response = self.client.post(self.url, self._payload(), format="json")
        contest_team_id = create_response.json()["id"]
        original_team_id = create_response.json()["team"]
        pilot_id = Team.objects.get(pk=original_team_id).crew.member1_id

        # A realistic edit keeps the same pilot ("existing" mode, not "create" again - which
        # would try to create a second Person with the same email and hit Person.validate()'s
        # duplicate-email guard) while changing the aircraft.
        response = self.client.post(
            self.url,
            self._payload(
                contest_team=contest_team_id,
                pilot={"mode": "existing", "person": pilot_id},
                aeroplane={"registration": "LN-REPLACED", "type": "Piper", "colour": "Blue"},
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        new_team_id = response.json()["team"]
        self.assertNotEqual(new_team_id, original_team_id)
        self.assertFalse(ContestTeam.objects.filter(contest=self.contest, team_id=original_team_id).exists())
        self.assertTrue(ContestTeam.objects.filter(contest=self.contest, team_id=new_team_id).exists())

    @override_settings(ACCESS_ENFORCEMENT_MODE="enforce", DEFAULT_FREE_CONTESTANT_LIMIT=0)
    def test_capacity_rejection_leaves_no_new_rows(self):
        person_count_before = Person.objects.count()
        team_count_before = Team.objects.count()
        contest_team_count_before = ContestTeam.objects.count()

        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(Person.objects.count(), person_count_before)
        self.assertEqual(Team.objects.count(), team_count_before)
        self.assertEqual(ContestTeam.objects.count(), contest_team_count_before)

    @override_settings(ACCESS_ENFORCEMENT_MODE="enforce", DEFAULT_FREE_CONTESTANT_LIMIT=0)
    def test_owner_team_bypasses_capacity_limit(self):
        owner_person = Person.objects.create(first_name="Owner", last_name="Person", email=self.owner.email)
        response = self.client.post(
            self.url,
            self._payload(pilot={"mode": "existing", "person": owner_person.pk}),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)


class TestImportTeamsApi(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="import-owner@example.com", password="secret")
        self.owner.user_permissions.add(Permission.objects.get(codename="add_contest"))
        self.source_contest = _make_contest(self.owner, name="Import source contest")
        self.target_contest = _make_contest(self.owner, name="Import target contest")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

        pilot = Person.objects.create(first_name="Import", last_name="Pilot", email="import-pilot@example.com")
        from display.models import Crew

        crew = Crew.objects.create(member1=pilot)
        aeroplane = Aeroplane.objects.create(registration="LN-IMPORT")
        club = Club.objects.create(name="Import Club", country="NO")
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane, club=club)
        self.source_contest_team = ContestTeam.objects.create(contest=self.source_contest, team=self.team, air_speed=80)

    def test_imports_teams_from_another_contest(self):
        response = self.client.post(
            f"/api/v1/contests/{self.target_contest.pk}/import_teams/",
            {"source_contest": self.source_contest.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertTrue(ContestTeam.objects.filter(contest=self.target_contest, team=self.team).exists())
        # Source registration is untouched by the copy.
        self.assertTrue(
            ContestTeam.objects.filter(pk=self.source_contest_team.pk, contest=self.source_contest).exists()
        )

    def test_import_teams_requires_source_contest(self):
        response = self.client.post(
            f"/api/v1/contests/{self.target_contest.pk}/import_teams/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
