import threading

import datetime


class TimedOut(BaseException):
    pass


class TimedQueue:
    def __init__(self):
        self._ready_event = threading.Event()
        self._lock = threading.Lock()
        self._queue = []
        self._closed = False

    def empty(self):
        with self._lock:
            return len(self._queue) == 0

    def qsize(self):
        with self._lock:
            return len(self._queue)

    def close(self):
        self._closed = True
        self._ready_event.set()

    def put(self, data, stamp: datetime.datetime):
        with self._lock:
            if not self._queue or stamp >= self._queue[-1][1]:
                self._queue.append((data, stamp))
            else:
                self._queue.append((data, stamp))
                # Should we sort the queue?
                self._queue.sort(key=lambda i: i[1])
            self._ready_event.set()

    def peek(self):
        try:
            return self._queue[0][0]
        except IndexError:
            return None

    def get(self, timeout: float = None):
        start = datetime.datetime.now(datetime.timezone.utc)
        while True:
            now = datetime.datetime.now(datetime.timezone.utc)
            with self._lock:
                if not self._queue:
                    if self._closed:
                        return None
                    internal_timeout = 10.0
                else:
                    data, stamp = self._queue[0]
                    if stamp <= now:
                        self._queue.pop(0)
                        return data
                    internal_timeout = (stamp - now).total_seconds()

            if timeout is not None:
                elapsed = (now - start).total_seconds()
                remaining = timeout - elapsed
                if remaining <= 0:
                    raise TimedOut
                internal_timeout = min(internal_timeout, remaining)
            
            if self._ready_event.wait(timeout=max(0, internal_timeout)):
                with self._lock:
                    if not self._closed:
                        self._ready_event.clear()
            else:
                # Timeout or time to release reached
                pass
