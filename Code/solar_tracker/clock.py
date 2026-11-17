"""Injectable clocks. All timestamps are timezone-aware UTC; intervals use monotonic()."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class SimClock:
    """Virtual clock. sleep() advances virtual time in sub-steps of at most 0.05 s and
    calls ``on_step(dt)`` for each so the simulated world evolves. Never waits."""

    MAX_STEP_S = 0.05

    def __init__(self, start_utc: datetime, on_step: Optional[Callable[[float], None]] = None):
        if start_utc.tzinfo is None or start_utc.utcoffset() != timedelta(0):
            raise ValueError("start_utc must be timezone-aware UTC")
        self.start_utc = start_utc
        self.on_step = on_step
        self._t = 0.0

    def now_utc(self) -> datetime:
        return self.start_utc + timedelta(seconds=self._t)

    def monotonic(self) -> float:
        return self._t

    def sleep(self, seconds: float) -> None:
        remaining = seconds
        while remaining > 1e-12:
            h = min(remaining, self.MAX_STEP_S)
            self._t += h
            remaining -= h
            if self.on_step is not None:
                self.on_step(h)
