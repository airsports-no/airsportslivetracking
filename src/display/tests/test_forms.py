import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.forms import ContestantForm
from display.models import Person, Contest, Route, NavigationTask, Crew, Aeroplane, Team


