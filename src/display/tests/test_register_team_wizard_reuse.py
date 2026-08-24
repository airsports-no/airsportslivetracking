import datetime

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from display.models import Aeroplane, Club, Contest, ContestTeam, Crew, Person, Team
from display.views_wizards import RegisterTeamWizard


class TestRegisterTeamWizardReusesExistingClubAndAeroplane(TestCase):
    """
    Regression test for the "A club with this name already exists" bug: selecting an existing
    club/aeroplane from the wizard's autocomplete must reuse the existing row instead of trying
    (and failing) to create a duplicate.
    """

    def setUp(self):
        self.user = get_user_model().objects.create(email="wizard-reuse@example.com")
        self.contest = Contest.objects.create(
            name="Wizard reuse contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
            created_by=self.user,
        )
        self.pilot = Person.objects.create(first_name="Existing", last_name="Pilot", email="pilot@example.com")
        self.existing_club = Club.objects.create(name="Existing Flying Club", country="NO")
        self.existing_aeroplane = Aeroplane.objects.create(registration="LN-ABC", type="Cessna", colour="White")

        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}

        self.wizard = RegisterTeamWizard()
        self.wizard.request = request
        self.wizard.kwargs = {"team_pk": None, "contest_pk": self.contest.pk}

        cleaned_data_by_step = {
            "member1search": {"person_id": self.pilot.pk},
            "member2search": {},
            "tracking": {
                "air_speed": 90,
                "tracking_service": "traccar",
                "tracking_device": "app_tracking_pilot_and_copilot",
                "tracker_device_id": None,
            },
            "aeroplane": {
                "registration": self.existing_aeroplane.registration,
                "type": "Cessna",
                "colour": "White",
                "picture": None,
                "picture_display_field": None,
            },
            "club": {
                "name": self.existing_club.name,
                "country": self.existing_club.country,
                "logo": None,
                "logo_display_field": None,
                "country_flag_display_field": None,
            },
        }
        self.wizard.get_cleaned_data_for_step = lambda step: cleaned_data_by_step.get(step)

        post_data_by_step = {
            "member1search": {"use_existing_pilot": "1"},
            "member2search": {"skip_copilot": "1"},
        }
        self.wizard.get_post_data_for_step = lambda step: post_data_by_step.get(step, {})

    def test_done_reuses_existing_club_and_aeroplane_without_error(self):
        club_count_before = Club.objects.count()
        aeroplane_count_before = Aeroplane.objects.count()

        response = self.wizard.done([], form_dict={})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Club.objects.count(), club_count_before)
        self.assertEqual(Aeroplane.objects.count(), aeroplane_count_before)

        team = Team.objects.get(club=self.existing_club, aeroplane=self.existing_aeroplane)
        self.assertEqual(team.crew.member1, self.pilot)
        self.assertTrue(ContestTeam.objects.filter(contest=self.contest, team=team).exists())
