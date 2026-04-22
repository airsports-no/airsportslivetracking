import os
import sys
import datetime
import logging
import django
from unittest.mock import patch
from utilities.mock_utilities import TraccarMock

# Setup django
# Assuming the script is run from /workspace or /workspace/src
sys.path.append("/workspace/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
django.setup()

# Configure logging (after django.setup to override its configuration)
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

from display.models import Contestant, ContestantReceivedPosition
from display.calculators.contestant_processor import ContestantProcessor
from redis_queue import RedisQueue

def recalculate_contestant(contestant):
    logger.info(f"Recalculating {contestant} (PK: {contestant.pk})")
    
    # Fetch existing positions before the processor deletes them in __init__
    positions = list(contestant.contestantreceivedposition_set.all().order_by('time'))
    if not positions:
        logger.info(f"No positions for {contestant}, skipping")
        return
    
    logger.info(f"Found {len(positions)} positions for {contestant}")
    
    # Convert to format expected by ContestantProcessor.generate_position_block_for_contestant
    traccar_positions = []
    device_id = contestant.tracker_device_id or "unknown"
    for i, p in enumerate(positions):
        traccar_positions.append({
            "deviceId": device_id,
            "id": i,
            "latitude": float(p.latitude),
            "longitude": float(p.longitude),
            "altitude": float(p.altitude),
            "attributes": {
                "batteryLevel": p.battery_level,
                "course": p.course
            },
            "speed": float(p.speed),
            "course": float(p.course),
            "device_time": p.time,
        })
    
    # Ensure ContestantTrack exists
    from display.models import ContestantTrack
    ct, created = ContestantTrack.objects.get_or_create(
        contestant=contestant, 
        defaults={"score": contestant.navigation_task.scorecard.initial_score}
    )
    if created:
        logger.info(f"Created missing ContestantTrack for {contestant}")
    
    # Push to Redis queue
    queue_name = f"recalculate_{contestant.pk}"
    q = RedisQueue(queue_name)
    # Clear queue first if it exists
    while not q.empty():
        try:
            q.pop()
        except:
            break
    
    for p in traccar_positions:
        q.append(p)
    q.append(None) # Signal end of track
    
    # Temporarily set delay to 0 for fast batch processing
    task = contestant.navigation_task
    original_delay = task.calculation_delay_minutes
    if original_delay != 0:
        logger.info(f"Temporarily setting calculation_delay_minutes to 0 for task {task}")
        task.calculation_delay_minutes = 0
        task.save(update_fields=['calculation_delay_minutes'])
    
    try:
        # Create and run processor
        # live_processing=False ensures it doesn't try to fetch more data from external services
        processor = ContestantProcessor(contestant, live_processing=False, queue_name_override=queue_name, recalculate=True)
        processor.run()
        logger.info(f"Successfully recalculated {contestant}")
    except Exception as e:
        logger.exception(f"Failed to recalculate {contestant}: {e}")
    finally:
        # Restore delay
        if original_delay != 0:
            task.calculation_delay_minutes = original_delay
            task.save(update_fields=['calculation_delay_minutes'])
        
        # Clean up queue
        while not q.empty():
            try:
                q.pop()
            except:
                break

PROGRESS_FILE = "recalc_progress.log"

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_progress(contestant_pk):
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"{contestant_pk}\n")

def main():
    completed_pks = load_progress()
    contestants = Contestant.objects.all().order_by('navigation_task', 'contestant_number')
    total = contestants.count()
    logger.info(f"Starting recalculation of {total} contestants. {len(completed_pks)} already completed.")
    
    # Mock traccar and slack facade to avoid errors
    with patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock), \
         patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock), \
         patch("display.signals.get_traccar_instance", return_value=TraccarMock), \
         patch("display.calculators.contestant_processor.post_slack_competition_message"):
        
        for i, contestant in enumerate(contestants):
            if str(contestant.pk) in completed_pks:
                logger.info(f"Skipping already completed contestant {contestant} (PK: {contestant.pk})")
                continue

            print(f"Processing {i+1}/{total} (PK: {contestant.pk}) - {contestant}")
            logger.info(f"--- Processing {i+1}/{total}: {contestant} ---")
            try:
                recalculate_contestant(contestant)
                save_progress(contestant.pk)
            except Exception as e:
                logger.error(f"Error during recalculation of {contestant}: {e}")
    
    logger.info("Recalculation complete")

if __name__ == "__main__":
    main()
