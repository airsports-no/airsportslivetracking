import datetime
import logging
import os
from typing import Optional

import redis_lock
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import connections
from celery.schedules import crontab
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from redis.client import Redis

from display.calculators.contestant_processor import ContestantProcessor
from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.utils import timezone

from display.models.contestant import Contestant
from display.models.email_map_link import EmailMapLink
from display.models.flymaster_data import FlymasterData
from display.utilities.calculator_running_utilities import is_calculator_running
from display.utilities.calculator_termination_utilities import is_termination_requested
from live_tracking_map.celery import app
from live_tracking_map.settings import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

# generate_flight_orders/map_plotter (matplotlib+cartopy), playback_tools, and
# position_processor_process are all imported lazily inside the tasks that
# actually use them, not at module scope. Every task in this module (including
# run_live_contestant_calculator below) is defined by importing this module,
# so a module-scope import here was pure cold-start tax for tasks that never
# touch plotting - it also runs in the live_calculator pool, which never
# plots anything and pays this cost on every forked worker process.

logger = logging.getLogger(__name__)


@app.task
def generate_map_async(task_id: int, contestant_id: Optional[int], map_params: dict, user_id: int):
    try:
        from display.models import NavigationTask, Contestant
        from django.contrib.auth import get_user_model
        from display.flight_order_and_maps.generate_flight_orders import embed_map_in_pdf
        from display.flight_order_and_maps.map_plotter import plot_route

        task = NavigationTask.objects.get(pk=task_id)
        contestant = Contestant.objects.get(pk=contestant_id) if contestant_id else None
        user = get_user_model().objects.get(pk=user_id)

        logger.info(f"Async map generation started for task {task_id}, contestant {contestant_id}")

        map_source = map_params["map_source"]

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
            line_width=float(map_params["line_width"]),
            minute_mark_line_width=float(map_params.get("minute_mark_line_width", 0.5)),
            colour=map_params["colour"],
            include_meridians_and_parallels_lines=map_params["include_meridians_and_parallels_lines"],
            include_openaip_overlay=map_params.get("include_openaip_overlay", False),
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
        from playback_tools.playback import recalculate_live_contestant

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
        from playback_tools.playback import recalculate_from_existing_positions_sync

        recalculate_from_existing_positions_sync(contestant)
    except:
        logger.exception("Exception in recalculate_existing_positions")


@app.task(queue="live_calculator")
def run_live_contestant_calculator(contestant_pk: int):
    """
    Runs a contestant's live-tracking calculator to completion. Dispatched
    from add_positions_to_calculator (position_processor_process.py) onto a
    dedicated queue/worker pool, replacing the previous one-Kubernetes-Job-
    per-contestant model. CELERY_TASK_ACKS_LATE/CELERY_TASK_REJECT_ON_WORKER_LOST
    (settings.py) mean a worker dying mid-task (Spot preemption, a worker-pool
    deploy) gets this task requeued onto another worker automatically;
    ContestantProcessor's idempotent-restart handling (see
    contestant_processor.py and the ScoreLogEntry idempotency constraint)
    makes that resume safe.

    That requeue-on-worker-loss path is also why this needs an explicit
    running check: the broker's visibility timeout can redeliver a message
    for a task that is, in fact, still running (see
    CELERY_BROKER_TRANSPORT_OPTIONS in settings.py), and a worker restart used
    to call restore_all_unacknowledged_messages() unconditionally on boot,
    requeueing every in-flight task cluster-wide. Without the check below,
    either of those turns into a second ContestantProcessor racing the first
    one on the same contestant.
    """
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.warning(f"Attempting to start calculator for non-existent contestant {contestant_pk}")
        return
    if contestant.contestanttrack.calculator_finished or is_termination_requested(contestant_pk):
        logger.warning(f"Attempting to start calculator for terminated contestant {contestant}")
        return
    if is_calculator_running(contestant_pk):
        logger.info(f"Calculator already running for {contestant}, ignoring redelivered/duplicate dispatch")
        return
    try:
        contestant_processor = ContestantProcessor(contestant, live_processing=True)
    except (DjangoValidationError, DRFValidationError) as exc:
        logger.warning(f"Refusing to start calculator for contestant {contestant_pk}: {exc}")
        return
    contestant_processor.run()


@app.task
def import_gpx_track(contestant_pk: int, gpx_file: str):
    try:
        contestant = Contestant.objects.get(pk=contestant_pk)
    except ObjectDoesNotExist:
        logger.exception("Could not find contestant for contestant key {}".format(contestant_pk))
        return
    logger.info(f"{contestant}: About to insert GPX file")
    try:
        from playback_tools.playback import insert_gpx_file

        insert_gpx_file(contestant, gpx_file.encode("utf-8"))
    except:
        logger.exception("Exception in import_gpx_track")


def append_cache_dict(cache_key, dict_key, value):
    conn = Redis(REDIS_HOST, REDIS_PORT, 2, password=REDIS_PASSWORD)
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
            from display.flight_order_and_maps.generate_flight_orders import generate_flight_orders

            orders = generate_flight_orders(contestant)
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
def generate_editable_route_thumbnail(editable_route_id: int):
    from display.models import EditableRoute

    try:
        editable_route = EditableRoute.objects.get(pk=editable_route_id)
    except EditableRoute.DoesNotExist:
        logger.warning(f"EditableRoute {editable_route_id} no longer exists, skipping thumbnail generation")
        return

    editable_route.update_thumbnail()


@app.task
def process_user_uploaded_map(map_id: int):
    """
    Generate the thumbnail and detect the zoom range for a newly uploaded or updated UserUploadedMap.

    Heavy mbtiles processing (streaming the file locally, stitching tiles into a thumbnail image) is run
    out-of-band to avoid blocking the gunicorn request worker and exceeding its memory/timeout limits.
    """
    from display.models import UserUploadedMap

    try:
        instance = UserUploadedMap.objects.get(pk=map_id)
    except UserUploadedMap.DoesNotExist:
        logger.warning(f"UserUploadedMap {map_id} no longer exists, skipping processing")
        return

    try:
        instance.clear_local_file_path()
        content, minimum_zoom, maximum_zoom = instance.create_thumbnail()
        filename = os.path.split(instance.map_file.name)[1] + "_thumbnail.png"
        try:
            instance.thumbnail.save(filename, ContentFile(content.getvalue()), save=False)
        except Exception:
            logger.exception(f"Failed saving thumbnail for UserUploadedMap {map_id}")
        instance.minimum_zoom_level = minimum_zoom
        instance.maximum_zoom_level = maximum_zoom
        try:
            minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude = instance.get_bounds()
            instance.minimum_longitude = minimum_longitude
            instance.minimum_latitude = minimum_latitude
            instance.maximum_longitude = maximum_longitude
            instance.maximum_latitude = maximum_latitude
        except Exception:
            logger.exception(f"Failed reading bounds for UserUploadedMap {map_id}")
        if not minimum_zoom <= instance.default_zoom_level <= maximum_zoom:
            clamped = max(minimum_zoom, min(instance.default_zoom_level, maximum_zoom))
            logger.warning(
                f"Clamping default_zoom_level for UserUploadedMap {map_id} from "
                f"{instance.default_zoom_level} to {clamped} (map supports [{minimum_zoom}, {maximum_zoom}])"
            )
            instance.default_zoom_level = clamped
        if instance.published_relative_path and instance.published_service_key:
            service_key = instance.published_service_key
            relative_path = instance.published_relative_path
        else:
            service_key = instance.default_service_key
            relative_path = instance.default_published_relative_path
        instance.published_service_key = service_key
        instance.published_relative_path = relative_path
        instance.published_at = timezone.now()
        request_mbtiles_reload()
        instance.processing_status = UserUploadedMap.PROCESSING_READY
        instance.processing_error = ""
        instance.save()
    except Exception as ex:
        logger.exception(f"Failed processing UserUploadedMap {map_id}")
        UserUploadedMap.objects.filter(pk=map_id).update(
            processing_status=UserUploadedMap.PROCESSING_FAILED,
            processing_error=f"Failed reading mbtiles file: {ex}",
        )


@app.task
def process_flymaster_file(file_data: str):
    from display.flymaster_position_builder import build_positions_from_flymaster
    from position_processor_process import add_positions_to_calculator

    contestant, identifier, positions = build_positions_from_flymaster(file_data)
    if contestant is not None:
        add_positions_to_calculator(contestant, positions)
    if len(positions) > 0:
        FlymasterData.objects.create(identifier=identifier, timestamp=positions[0]["device_time"], data=file_data)
        if not contestant:
            logger.info(
                f"Could not find contestant for fly master identifier {identifier} at timestamp {positions[0]["device_time"]}"
            )
