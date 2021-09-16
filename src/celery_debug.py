from display.tasks import generate_and_notify_flight_order, debug
debug.apply_async()
generate_and_notify_flight_order.apply_async((2, "frankose@ifi.uio.no", "Frank Olaf"))


from display.tasks import generate_and_notify_flight_order
generate_and_notify_flight_order(2238, "frankose@ifi.uio.no", "Frank Olaf")
