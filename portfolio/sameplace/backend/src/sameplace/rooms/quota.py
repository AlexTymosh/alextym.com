"""Best-effort process-local storage cooldown; not a global billing meter."""

from threading import Lock
from time import monotonic


def quota_error(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if type(error).__name__ == "ResourceExhausted" or getattr(error, "code", None) == 8:
            return True
        error = error.__cause__ or error.__context__
    return False


class QuotaCircuit:
    def __init__(self, clock=monotonic):
        self.clock = clock
        self.lock = Lock()
        self.until = 0.0

    def remaining(self):
        with self.lock:
            return max(0, int(self.until - self.clock() + 0.999))

    def observe(self, error):
        if quota_error(error):
            with self.lock:
                if self.until <= self.clock():
                    self.until = self.clock() + 120
