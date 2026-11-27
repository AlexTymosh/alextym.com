"""Bounded process-local request pressure guard, not a durable authorization rule."""

from threading import Lock
from time import monotonic


class RequestLimiter:
    def __init__(self, clock=monotonic):
        self.clock = clock
        self.lock = Lock()
        self.window = -1
        self.total = 0
        self.users: dict[str, int] = {}

    def allow(self, uid):
        with self.lock:
            window = int(self.clock() // 60)
            if window != self.window:
                self.window = window
                self.total = 0
                self.users.clear()
            count = self.users.get(uid, 0)
            if self.total >= 180 or count >= 30:
                return False
            self.total += 1
            self.users[uid] = count + 1
            return True
