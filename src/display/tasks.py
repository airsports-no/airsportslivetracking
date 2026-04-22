import datetime
import logging
from typing import Optional

import redis_lock
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import connections
from celery.schedules import crontab
from django.core.exceptions import ObjectDoesNotExist
from redis.client import Redis

from display.flight_order_and_maps.generate_flight_orders import (
    generate_flight_orders_latex,
    embed_map_in_pdf,
)
from display.flight_order_and_maps.map_plotter import plot_route
from django.core.files.storage import default_storage
from django.utils.text import slugify

from display.models.contestant import Contestant
from display.models.email_map_link import EmailMapLink
from display.models.flymaster_data import FlymasterData
from live_tracking_map.celery import app
from live_tracking_map.settings import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from playback_tools.playback import (
    recalculate_live_contestant,
    insert_gpx_file,
    recalculate_from_existing_positions_sync,
)
from position_processor_process import add_positions_to_calculator

logger = logging.getLogger(__name__)


@app.task
def generate_map_async(task_id: int, contestant_id: Optional[int], map_params: dict, user_id: int):
    try:
        from display.models import NavigationTask, Contestant
        from django.contrib.auth import get_user_model

        task = NavigationTask.objects.get(pk=task_id)
        contestant = Contestant.objects.get(pk=contestant_id) if contestant_id else None
        user = get_user_model().objects.get(pk=user_id)

        logger.info(f"Async map generation started for task {task_id}, contestant {contestant_id}")

        map_source = map_params["map_source"]
        user_map_source = None
        if map_params.get("user_map_source_id"):
            from display.models import UserUploadedMap

            try:
                user_map_source = UserUploadedMap.objects.get(pk=map_params["user_map_source_id"])
            except UserUploadedMap.DoesNotExist:
                pass

        # Use existing plot_route logic
        map_image = plot_route(
            task,
            map_params["size"],
            zoom_level=int(map_params["zoom_level"]),
            landscape=map_params["landscape"],
            contestant=contestant,
            annotations=map_params["annotations"],
            waypoints_only=map_params["waypoints_only"],
            dpi=map_params["dpi"],
            scale=int(map_params["scale"]),
            map_source=map_source,
            user_map_source=user_map_source,
            line_width=float(map_params["line_width"]),
            minute_mark_line_width=float(map_params.get("minute_mark_line_width", 0.5)),
            colour=map_params["colour"],
            include_meridians_and_parallels_lines=map_params["include_meridians_and_parallels_lines"],
            margins_mm=map_params.get("margin", 10),
        )

        # Convert to PDF using existing logic
        from display.flight_order_and_maps.map_constants import A4
        from display.flight_order_and_maps.map_plotter import A4_WIDTH, A3_WIDTH, A4_HEIGHT, A3_HEIGHT

        margin = map_params.get("margin", 10)
        pdf = embed_map_in_pdf(
            "a4paper" if map_params["size"] == A4 else "a3paper",
            map_image.read(),
            10 * A4_WIDTH - 2 * margin if map_params["size"] == A4 else 10 * A3_WIDTH - 2 * margin,
            10 * A4_HEIGHT - 2 * margin if map_params["size"] == A4 else 10 * A3_HEIGHT - 2 * margin,
            map_params["landscape"],
        )

        # Save to storage
        filename = f"generated_maps/{task_id}/"
        if contestant:
            filename += f"contestant_{contestant_id}_{slugify(contestant.team)}.pdf"
        else:
            filename += f"task_{task_id}_{slugify(task.name)}.pdf"

        # Use timestamp to avoid cache issues
        filename = f"{filename.replace('.pdf', '')}_{int(datetime.datetime.now().timestamp())}.pdf"

        file_path = default_storage.save(filename, ContentFile(pdf))
        file_url = default_storage.url(file_path)

        # Store in cache for the status page
        cache_key = f"map_gen_result_{task_id}_{contestant_id}_{user_id}"
        cache.set(cache_key, {"status": "complete", "url": file_url}, timeout=3600)
        logger.info(f"Async map generation complete. URL: {file_url}")

    except Exception as e:
        logger.exception("Failed async map generation")
        cache_key = f"map_gen_result_{task_id}_{contestant_id}_{user_id}"
        cache.set(cache_key, {"status": "error", "message": str(e)}, timeout=3600)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Executes every morning at 7:30 a.m.
    sender.add_periodic_task(
        crontab(hour=7, minute=30, day_of_week="*"),
        delete_old_flight_orders.s(),
    )
    sender.add_periodic_task(10, debug.s())


@app.task
def debug():
    print(debug)


@app.task
def recalculate_live_data_for_contestant(contestant_pk: int):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    logger.info(f"{contestant}: About recalculate traccar track")
    try:
        recalculate_live_contestant(contestant)
    except:
        logger.exception("Exception in revert_gpx_track_to_traccar")


@app.task
def recalculate_existing_positions(contestant_pk: int):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    logger.info(f"{contestant}: About to recalculate from existing positions")
    try:
        recalculate_from_existing_positions_sync(contestant)
    except:
        logger.exception("Exception in recalculate_existing_positions")


@app.task
def import_gpx_track(contestant_pk: int, gpx_file: str):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    logger.info(f"{contestant}: About to insert GPX file")
    try:
        insert_gpx_file(contestant, gpx_file.encode("utf-8"))
    except:
        logger.exception("Exception in import_gpx_track")


def append_cache_dict(cache_key, dict_key, value):
    conn = Redis(REDIS_HOST, REDIS_PORT, 2)  # , REDIS_PASSWORD)
    base = cache_key
    with redis_lock.Lock(conn, f"{base}_lock"):
        dictionary = cache.get(cache_key) or {}
        dictionary[dict_key] = value
        cache.set(cache_key, dictionary)


@app.task
def generate_and_maybe_notify_flight_order(
    contestant_pk: int, email: str, first_name: str, transmit_immediately: bool = False
):
    try:
        try:
            contestant = Contestant.objects.get(pk=contestant_pk)
        except ObjectDoesNotExist:
            logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
            return
        logger.info(f"Generating flight order for {contestant}")
        append_cache_dict(f"completed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, False)
        try:
            orders = generate_flight_orders_latex(contestant)
            for c in connections.all():
                c.close_if_unusable_or_obsolete()
            contestant.emailmaplink_set.all().delete()
            mail_link = EmailMapLink.objects.create(contestant=contestant, orders=bytes(orders))
            if transmit_immediately:
                mail_link.send_email(email, first_name)
        except Exception as e:
            append_cache_dict(
                f"generate_failed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, str(e)
            )
            raise
        for c in connections.all():
            c.close_if_unusable_or_obsolete()
        append_cache_dict(f"completed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, True)
    except:
        logger.exception("Exception in generate_flight_order")


@app.task
def notify_flight_order(contestant_pk: int, email: str, first_name: str):
    try:
        try:
            contestant = Contestant.objects.get(pk=contestant_pk)
        except ObjectDoesNotExist:
            logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
            return
        try:
            mail_link = EmailMapLink.objects.filter(contestant=contestant).first()
            mail_link.send_email(email, first_name)
        except Exception as e:
            append_cache_dict(
                f"transmit_failed_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, str(e)
            )
            raise
        for c in connections.all():
            c.close_if_unusable_or_obsolete()
        append_cache_dict(f"transmitted_flight_orders_map_{contestant.navigation_task.pk}", contestant.pk, True)
    except:
        logger.exception("Exception in notify_flight_order")


@app.task
def delete_old_flight_orders():
    EmailMapLink.objects.filter(
        contestant__finished_by_time__lt=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
    ).delete()


@app.task
def process_flymaster_file(file_data: str):
    contestant, identifier, positions = build_positions_from_flymaster(file_data)
    if contestant is not None:
        add_positions_to_calculator(contestant, positions)
    if len(positions) > 0:
        FlymasterData.objects.create(identifier=identifier, timestamp=positions[0]["device_time"], data=file_data)
        if not contestant:
            logger.info(
                f"Could not find contestant for fly master identifier {identifier} at timestamp {positions[0]["device_time"]}"
            )
