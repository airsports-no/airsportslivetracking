import datetime
import logging

import django
from django.core.exceptions import ObjectDoesNotExist
from django.db import OperationalError, connection

from display.models import Person, Contestant
from display.serialisers import PersonLtdSerialiser
from live_tracking_map.settings import LIVE_POSITION_TRANSMITTER_CACHE_RESET_INTERVAL, PURGE_GLOBAL_MAP_INTERVAL
from position_processor_process import PERSON_TYPE
from websocket_channels import WebsocketFacade

logger = logging.getLogger(__name__)


def live_position_transmitter_process(queue):
    websocket_facade = WebsocketFacade()
    django.db.connections.close_all()
    person_cache = {}
    contestant_cache = {}
    last_reset = datetime.datetime.now()

    def fetch_person(person_or_contestant):
        try:
            person = person_cache[person_or_contestant]
        except KeyError:
            person = Person.objects.get(app_tracking_id=person_or_contestant)
            person_cache[person_or_contestant] = person
            logger.info(f"Found person for live position {person}")
        return person

    def fetch_contestant(person_or_contestant):
        try:
            contestant = contestant_cache[person_or_contestant]
        except KeyError:
            contestant = (
                Contestant.objects.filter(pk=person_or_contestant)
                .select_related(
                    "navigation_task",
                    "team",
                    "team__crew",
                    "team__crew__member1",
                    "team__crew__member2",
                    "team__aeroplane",
                )
                .first()
            )
            logger.info(f"Found contestant for live position {contestant}")
            contestant_cache[person_or_contestant] = contestant
        return contestant

    while True:
        (
            data_type,
            person_or_contestant,
            position_data,
            device_time,
            is_simulator,
        ) = queue.get()
        if (datetime.datetime.now() - last_reset).total_seconds() > LIVE_POSITION_TRANSMITTER_CACHE_RESET_INTERVAL:
            person_cache = {}
            contestant_cache = {}
            last_reset = datetime.datetime.now()

        navigation_task_id = None
        global_tracking_name = None
        person_data = None
        push_global = True
        if data_type == PERSON_TYPE:
            try:
                person = fetch_person(person_or_contestant)
                person.last_seen = device_time
                person.save(update_fields=["last_seen"])
                global_tracking_name = person.app_aircraft_registration
                if person.is_public:
                    person_data = PersonLtdSerialiser(person).data
            except ObjectDoesNotExist:
                pass
            except OperationalError:
                logger.warning(
                    f"Error when fetching person for app_tracking_id '{person_or_contestant}'. Attempting to reconnect"
                )
                connection.connect()
            except Exception:
                logger.exception(f"Something failed when trying to update person {person_or_contestant}")

        else:
            try:
                contestant = fetch_contestant(person_or_contestant)
                if contestant is not None:
                    global_tracking_name = contestant.team.aeroplane.registration
                    try:
                        person = contestant.team.crew.member1
                        person.last_seen = device_time
                        person.save(update_fields=["last_seen"])
                        if person.is_public:
                            person_data = PersonLtdSerialiser(person).data
                    except:
                        logger.exception(f"Failed fetching person data for contestant {contestant}")
                    if contestant.navigation_task.everything_public:
                        navigation_task_id = contestant.navigation_task_id
            except OperationalError:
                logger.warning(
                    f"Error when fetching contestant for app_tracking_id '{person_or_contestant}'. Attempting to reconnect"
                )
                connection.connect()
        now = datetime.datetime.now(datetime.timezone.utc)
        if (
            global_tracking_name is not None
            and not is_simulator
            and now < device_time + datetime.timedelta(seconds=PURGE_GLOBAL_MAP_INTERVAL)
        ):
            if push_global:
                websocket_facade.transmit_global_position_data(
                    global_tracking_name,
                    person_data,
                    position_data,
                    device_time,
                    navigation_task_id,
                )
            websocket_facade.transmit_airsports_position_data(
                global_tracking_name,
                position_data,
                device_time,
                navigation_task_id,
            )
