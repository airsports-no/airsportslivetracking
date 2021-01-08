import datetime

import pytz

summer = datetime.datetime( 2020, 8, 1, 12, tzinfo=datetime.timezone.utc)
print(summer.astimezone(pytz.timezone("Europe/Oslo")))
winter = datetime.datetime( 2020, 12, 1, 12, tzinfo=datetime.timezone.utc)
print(winter.astimezone(pytz.timezone("Europe/Oslo")))