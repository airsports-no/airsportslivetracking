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
    def size(self)->int:
        return self.redis_handle.llen(self.queue_name)

    def pop(self, blocking=False, timeout: float = 10) -> Any:
        if self.redis_handle:
            if not blocking:
                item = self.redis_handle.lpop(self.queue_name)
                if item is None:
                    raise RedisEmpty
            else:
                item = self.redis_handle.blpop([self.queue_name], timeout=timeout)
                if item is None:
                    raise RedisEmpty
                q, item = item
            try:
                return pickle.loads(item)
            except:
                logger.exception("Failed decoding queued item pop")
        return None

    def peek(self) -> Any:
        # logger.debug("Peak {}".format(self.queue_name))
        if self.redis_handle:
            item = self.redis_handle.lindex(self.queue_name, 0)
            # logger.debug("Got item {}".format(item))
            if item is None:
                raise RedisEmpty
            try:
                return pickle.loads(item)
            except:
                logger.exception("Failed decoding queued item peek")
        return None

    def empty(self) -> bool:
        try:
            self.peek()
            return False
        except RedisEmpty:
            return True
