import os

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from influx_facade import InfluxFacade

influx = InfluxFacade()
result_set = influx.get_positions_for_contestant(215, "2014-01-01T00:00:00Z")
print(result_set)
print(influx.get_number_of_positions_in_database())