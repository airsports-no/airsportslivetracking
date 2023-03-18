import time
from androidhelper import Android

droid = Android()
droid.startLocating()
locproviders = droid.locationProviders().result
print("locproviders:" + repr(locproviders))

gpsprovider = droid.locationProviderEnabled('gps').result
print("gpsprovider:" + repr(gpsprovider))
i = 0
while i < 100:
    event = droid.eventWaitFor('location', 10000).result
    print("Event:" + repr(event))

    location = droid.readLocation().result

    if len(location) > 0:
        print('Location:' + repr(location))

    else:
        location = droid.getLastKnownLocation().result
        print("Last location:" + repr(location))

    loc = location['network']  # change to gps if you can get it
    addr = droid.geocode(loc['latitude'], loc['longitude']).result
    print("addr:" + repr(addr))

    time.sleep(1)
    i = i + 1

droid.stopLocating()