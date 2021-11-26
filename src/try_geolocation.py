from display.utilities import get_country_code_from_location
from display.models import Contest

for contest in Contest.objects.all():
    if contest.latitude != 0 and contest.longitude != 0:
        contest.country = get_country_code_from_location(contest.latitude, contest.longitude)
        print(contest)
    contest.save()


print(get_country_code_from_location( 60, 11))

