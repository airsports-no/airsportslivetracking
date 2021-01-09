import datetime

import pytz

summer = datetime.datetime( 2020, 8, 1, 12, tzinfo=datetime.timezone.utc)
print(summer.astimezone(pytz.timezone("Europe/Oslo")))
winter = datetime.datetime( 2020, 12, 1, 12, tzinfo=datetime.timezone.utc)
print(winter.astimezone(pytz.timezone("Europe/Oslo")))


midday = datetime.datetime(2021, 1, 9, 12)
# midday = midday.replace(tzinfo=pytz.timezone("Europe/Paris"))
midday = pytz.timezone("Europe/Paris").localize(midday)
print(midday)