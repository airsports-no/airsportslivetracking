from display.models import Contestant, Person
from display.tasks import generate_and_notify_flight_order, debug
debug.apply_async()
generate_and_notify_flight_order.apply_async((2, "frankose@ifi.uio.no", "Frank Olaf"))


from display.tasks import generate_and_notify_flight_order
generate_and_notify_flight_order(2238, "frankose@ifi.uio.no", "Frank Olaf")

p = Person.objects.get(app_tracking_id="fGULB0jeSRp6xr9TLl7w7Sr9Ga2Z")
print(p)
c=Contestant.objects.get(pk = 2244)
print(c.tracker_start_time)