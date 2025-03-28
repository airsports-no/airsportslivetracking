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

    def close(self):
        self._closed = True
        self._ready_event.set()

    def put(self, data, stamp: datetime.datetime):
        with self._lock:
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
        now = datetime.datetime.now(datetime.timezone.utc)
        while True:
            with self._lock:
                if len(self._queue) == 0 and self._closed:
                    return None
                internal_timeout = max(0, (self._queue[0][1] - now).total_seconds()) if len(self._queue) > 0 else 10
            if timeout is not None:
                remaining_external_timeout = timeout - (now - start).total_seconds()
                internal_timeout = min(remaining_external_timeout, internal_timeout)
            self._ready_event.wait(timeout=internal_timeout)
            self._ready_event.clear()
            now = datetime.datetime.now(datetime.timezone.utc)
            with self._lock:
                if len(self._queue) > 0:
                    data, stamp = self._queue[0]
                    if stamp < now:
                        self._queue.pop(0)
                        return data
            if timeout is not None and (now - start).total_seconds() >= timeout:
                raise TimedOut
