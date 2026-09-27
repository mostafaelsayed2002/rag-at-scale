import time
from contextlib import contextmanager


class Stopwatch:
    """Times the parts of a request, so a slow answer says which part to fix."""

    def __init__(self):
        self.stages: dict[str, float] = {}

    @contextmanager
    def __call__(self, stage: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.stages[stage] = round((time.perf_counter() - started) * 1000, 2)
