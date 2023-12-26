import datetime
import logging
import typing
from typing import Optional

import requests
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import QuerySet
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from phonenumbers import PhoneNumber

from live_tracking_map import settings

if typing.TYPE_CHECKING:
    from display.models import MyUser

logger = logging.getLogger(__name__)


class Person(models.Model):
    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = PhoneNumberField(blank=True, null=True)
    creation_time = models.DateTimeField(
        auto_now_add=True,
        help_text="Used to figure out when a not validated personal and user should be deleted",
    )
    validated = models.BooleanField(
        default=True,
        help_text="Usually true, but set to false for persons created automatically during "
        "app API login. This is used to signify that the user profile must be "
        "updated. If this remains false for more than a few days, the person "
        "object and corresponding user will be deleted from the system.  This "
        "must therefore be set to True when submitting an updated profile from "
        "the app.",
    )
    app_tracking_id = models.CharField(
        max_length=28,
        editable=False,
        help_text="An automatically generated tracking ID which is distributed to the tracking app",
    )
    simulator_tracking_id = models.CharField(
        max_length=28,
        editable=False,
        help_text="An automatically generated tracking ID which is distributed to the simulator integration. Persons or contestants identified by this field should not be displayed on the global map.",
    )
    app_aircraft_registration = models.CharField(
        max_length=100,
        default="",
        blank=True,
        help_text="The display name of person positions on the global tracking map (should be an aircraft registration",
    )
    picture = models.ImageField(null=True, blank=True)
    biography = models.TextField(blank=True)
    country = CountryField(blank=True)
    is_public = models.BooleanField(
        default=False,
        help_text="If true, the person's name will be displayed together with the callsign on the global map",
    )
    last_seen = models.DateTimeField(null=True, blank=True)

    @property
    def is_tracking_active(self):
        return (
            # We assume the tracker is active if we have seen it today
            self.last_seen
            and datetime.datetime.now(datetime.timezone.utc).date() == self.last_seen.date()
        )

    @property
    def phone_country_prefix(self):
        phone = self.phone  # type: PhoneNumber
        return phone.country_code if phone else ""

    @property
    def phone_national_number(self):
        phone = self.phone  # type: PhoneNumber
        return phone.national_number if phone else ""

    @property
    def country_flag_url(self):
        if self.country:
            return self.country.flag
        return None

    @property
    def has_user(self):
        from display.models import MyUser

        return MyUser.objects.filter(email=self.email).exists()

    def __str__(self):
        return "{} {}".format(self.first_name, self.last_name)

    @classmethod
    def get_or_create(
        cls,
        first_name: Optional[str],
        last_name: Optional[str],
        phone: Optional[str],
        email: Optional[str],
    ) -> Optional["Person"]:
        possible_person: Optional[QuerySet] = None
        # if phone is not None and len(phone) > 0:
        #     possible_person = Person.objects.filter(phone=phone)
        if (not possible_person or possible_person.count() == 0) and email is not None and len(email) > 0:
            possible_person = Person.objects.filter(email__iexact=email)
        elif not possible_person or possible_person.count() == 0:
            if first_name is not None and len(first_name) > 0 and last_name is not None and len(last_name) > 0:
                possible_person = Person.objects.filter(
                    first_name__iexact=first_name, last_name__iexact=last_name
                ).first()
        if possible_person is None or possible_person.count() == 0:
            return Person.objects.create(phone=phone, email=email, first_name=first_name, last_name=last_name)
        return possible_person.first()

    def remove_profile_picture_background(self):
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            data={"image_url": self.picture.url, "size": "auto", "crop": "true"},
            headers={"X-Api-Key": settings.REMOVE_BG_KEY},
        )
        if response.status_code == requests.codes.ok:
            self.picture.save("nobg_" + self.picture.name, ContentFile(response.content))
            return None
        logger.error("Error:", response.status_code, response.text)
        return response.text

    def validate(self):
        if Person.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError("A person with this email already exists")


class Crew(models.Model):
    member1 = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="crewmember_one")
    member2 = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="crewmember_two",
    )

    @property
    def table_display(self):
        if self.member2:
            return "{}<br/>{}".format(self.member1, self.member2)
        return "{}".format(self.member1)

    def validate(self):
        if Crew.objects.filter(member1=self.member1, member2=self.member2).exclude(pk=self.pk).exists():
            raise ValidationError("A crew with this email already exists")

    def __str__(self):
        if self.member2:
            return "{} and {}".format(self.member1, self.member2)
        return "{}".format(self.member1)


class Club(models.Model):
    name = models.CharField(max_length=200)
    country = CountryField(blank=True)
    logo = models.ImageField(null=True, blank=True)

    # class Meta:
    #     unique_together = ("name", "country")

    def validate(self):
        if Club.objects.filter(name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError("A club with this name already exists")

    def __str__(self):
        return self.name

    @property
    def country_flag_url(self):
        if self.country:
            return self.country.flag
        return None


class Aeroplane(models.Model):
    registration = models.CharField(max_length=20)
    colour = models.CharField(max_length=40, blank=True)
    type = models.CharField(max_length=50, blank=True)
    picture = models.ImageField(null=True, blank=True)

    def __str__(self):
        return self.registration


class Team(models.Model):
    aeroplane = models.ForeignKey(Aeroplane, on_delete=models.PROTECT)
    crew = models.ForeignKey(Crew, on_delete=models.PROTECT)
    logo = models.ImageField(null=True, blank=True)
    country = CountryField(blank=True)
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return "{} in {}".format(self.crew, self.aeroplane)

    @property
    def table_display(self):
        return f"{self.crew.table_display}<br/>{self.aeroplane}"

    @property
    def country_flag_url(self):
        if self.country:
            return self.country.flag
        return None

    @classmethod
    def get_or_create_from_signup(
        cls, user: "MyUser", copilot: Person, aircraft_registration: str, club_name: str
    ) -> "Team":
        crew, _ = Crew.objects.get_or_create(member1=user.person, member2=copilot)
        aircraft, _ = Aeroplane.objects.get_or_create(registration=aircraft_registration)
        club, _ = Club.objects.get_or_create(name=club_name)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aircraft, club=club)
        return team
