# from display.utilities import get_country_code_from_location
# from display.models import Contest
#
# for contest in Contest.objects.all():
#     if contest.latitude != 0 and contest.longitude != 0:
#         contest.country = get_country_code_from_location(contest.latitude, contest.longitude)
#         print(contest)
#     contest.save()
#
#
# print(get_country_code_from_location( 60, 11))
#
import json

from geopy import Nominatim

geolocator = Nominatim(user_agent="airsports.no")
location = geolocator.reverse(f"60, 11")
print(json.dumps(location.raw))
