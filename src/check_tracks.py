import os



from influx_facade import InfluxFacade


influx = InfluxFacade()
print(influx.get_number_of_positions_in_database())
