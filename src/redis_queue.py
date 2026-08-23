import logging
import pickle
from typing import Dict, Any, List, Tuple

import redis

from live_tracking_map.settings import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

logger = logging.getLogger(__name__)


class RedisEmpty(Exception):
    pass


class RedisQueue:
    def __init__(self, queue_name: str, namespace: str = "contestant_processor_queue", subscribe: Dict = None):
        self.queue_name = f"{namespace}:{queue_name}"
        try:
            logger.debug("Attempting to connect to {}:{}".format(REDIS_HOST, REDIS_PORT))
            self.redis_handle = redis.StrictRedis(REDIS_HOST, REDIS_PORT, password=REDIS_PASSWORD)
            logger.info(
                "Connected RedisQueue to {}:{} with the queue {}".format(REDIS_HOST, REDIS_PORT, self.queue_name))
        except:
            self.redis_handle = None
            logger.exception("Failed connecting to redis host")
        if subscribe is not None:
            logger.debug("Initialising pubsub")
            self.pubsub = self.redis_handle.pubsub(ignore_subscribe_messages=False)
            logger.debug("Setting up subscriptions")
            self.pubsub.subscribe(**subscribe)
            logger.debug("Starting subscription thread")
            self.event_thread = self.pubsub.run_in_thread(sleep_time=1, daemon=True)
            self.event_thread.name = "redis_interface_subscriber"

    def append(self, item: Any):
        if self.redis_handle:
            self.redis_handle.rpush(self.queue_name, pickle.dumps(item))

    def push(self, item: Any):
        if self.redis_handle:
            self.redis_handle.lpush(self.queue_name, pickle.dumps(item))

    @property
    def size(self) -> int:
        if self.redis_handle:
            try:
                return self.redis_handle.llen(self.queue_name)
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                return 0
        return 0

    def pop(self, blocking=False, timeout: float = 10) -> Any:
        if self.redis_handle:
            if not blocking:
                item = self.redis_handle.lpop(self.queue_name)
                if item is None:
                    raise RedisEmpty
            else:
                try:
                    item = self.redis_handle.blpop([self.queue_name], timeout=timeout)
                except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                    # We re-raise these so the caller can distinguish between a sentinel None 
                    # and a transient infra failure.
                    raise

                if item is None:
                    raise RedisEmpty
                q, item = item
            try:
                val = pickle.loads(item)
                if val is None:
                    logger.info(f"RedisQueue {self.queue_name} received None sentinel")
                return val
            except Exception:
                logger.exception(f"Failed decoding queued item pop from {self.queue_name}. Item length: {len(item) if item else 'None'}")
                return None
        logger.error(f"RedisQueue {self.queue_name} has no redis_handle")
        return None


    def peek(self) -> Any:
        if self.redis_handle:
            try:
                item = self.redis_handle.lindex(self.queue_name, 0)
                if item is None:
                    raise RedisEmpty
                return pickle.loads(item)
            except RedisEmpty:
                raise
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                # If redis is down, we don't know if it's empty. 
                # Raise an error or return a sentinel? 
                # For safety in this app's logic, we'll return None and let the caller handle it,
                # but empty() needs to be careful.
                raise
            except Exception:
                logger.exception("Failed decoding queued item peek")
        return None

    def empty(self) -> bool:
        try:
            self.peek()
            return False
        except RedisEmpty:
            return True
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            # If redis is down, we should NOT assume it's empty and stop.
            # Returning False keeps the ingestion loop alive.
            return False
