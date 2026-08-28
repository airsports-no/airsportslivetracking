"""
Regression test for the critical finding (2026-08-28 security review): Crew.table_display /
Team.table_display interpolated raw Person/Aeroplane __str__ output (built from user-editable
first_name/last_name/registration) and was rendered with |safe in
navigationtask_detail.html - a pilot who set their name to a script payload got it executed in
a contest manager's session. Fixed by building the string with django.utils.html.format_html,
which escapes each interpolated value while keeping the <br/> as real markup.
"""

from django.test import SimpleTestCase, TestCase
from django.utils.safestring import SafeString

from display.models import Aeroplane, Crew, Person, Team


class TestCrewAndTeamTableDisplayEscaping(TestCase):
    def test_table_display_escapes_malicious_person_name(self):
        malicious_person = Person.objects.create(
            first_name="<img src=x onerror=alert(1)>", last_name="Pilot", email="attacker@example.com"
        )
        crew = Crew.objects.create(member1=malicious_person)

        result = crew.table_display

        self.assertIsInstance(result, SafeString)
        self.assertNotIn("<img", result)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", result)

    def test_table_display_escapes_both_crew_members(self):
        member1 = Person.objects.create(first_name="<b>1</b>", last_name="A", email="m1@example.com")
        member2 = Person.objects.create(first_name="<b>2</b>", last_name="B", email="m2@example.com")
        crew = Crew.objects.create(member1=member1, member2=member2)

        result = crew.table_display

        self.assertNotIn("<b>", result)
        self.assertIn("<br/>", result)  # the one deliberate piece of real markup survives

    def test_team_table_display_escapes_aeroplane_registration_and_keeps_crew_safe(self):
        person = Person.objects.create(first_name="Normal", last_name="Pilot", email="normal@example.com")
        crew = Crew.objects.create(member1=person)
        # Aeroplane.registration is max_length=20, so keep the payload short.
        aeroplane = Aeroplane.objects.create(registration="<b>XSS</b>")
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)

        result = team.table_display

        self.assertIsInstance(result, SafeString)
        self.assertNotIn("<b>XSS</b>", result)
        self.assertIn("&lt;b&gt;XSS&lt;/b&gt;", result)
        self.assertIn("Normal Pilot", result)
