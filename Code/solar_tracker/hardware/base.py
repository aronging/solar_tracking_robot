"""HAL interfaces and the code shared by both backends (spec section 8).

Angles in degrees, pulses in microseconds, currents in mA. The HAL itself enforces
servo soft limits, the slew rate and the calibrated pulse range.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

try:
    from typing import Protocol
except ImportError:                      # pragma: no cover - Python 3.7
    Protocol = object                    # type: ignore

from ..geometry import clamp

log = logging.getLogger("solar_tracker")


class HardwareError(RuntimeError):
    """A hardware call kept failing after retries."""


@dataclass(frozen=True)
class PanelReading:
    isc_mA: float        # mean over n samples
    isc_std_mA: float    # sample standard deviation
    n: int
    bus_V: float
    overrange: bool      # True if any sample > overrange_mA


@dataclass(frozen=True)
class ImuCal:            # BNO055 calibration status, each 0..3
    sys: int
    gyro: int
    accel: int
    mag: int


class Clock(Protocol):
    def now_utc(self) -> datetime: ...
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class PanelServos(Protocol):
    limits_deg: Tuple[float, float]
    def move_to(self, pan_deg: float, tilt_deg: float, settle_s: float = 0.0) -> Tuple[float, float]: ...
    def commanded(self) -> Tuple[float, float]: ...
    def pulses_us(self) -> Tuple[float, float]: ...


class PanelSensor(Protocol):
    def read(self, n_samples: int = 8) -> PanelReading: ...


class Imu(Protocol):
    def heading_deg(self) -> float: ...          # MAGNETIC heading, [0, 360)
    def calibration(self) -> ImuCal: ...


class DriveBase(Protocol):
    def set_turn(self, u: float) -> None: ...    # +u increases heading (clockwise from above)
    def stop(self) -> None: ...                  # idempotent, never raises


@dataclass
class Rig:
    clock: Any
    servos: Any
    panel: Any
    imu: Any
    drive: Any
    info: Dict[str, Any] = field(default_factory=dict)   # i2c scan, PCA9685 Hz, NTP, versions
    sim: Any = None                                      # SimWorld (ground truth) or None
    closer: Optional[Callable[[], None]] = None

    def close(self) -> None:
        """Stop the wheels and release the hardware. Never raises."""
        try:
            self.drive.stop()
        except Exception:
            pass
        if self.closer is not None:
            try:
                self.closer()
            except Exception:
                pass


def mean_std(samples) -> Tuple[float, float]:
    n = len(samples)
    mean = sum(samples) / n
    std = math.sqrt(sum((s - mean) ** 2 for s in samples) / (n - 1)) if n > 1 else 0.0
    return mean, std


@dataclass
class ServoCal:
    """angle_deg = m * (pulse_us - center_us) + c  (mean of the up and down fits)."""
    m: float
    c: float
    pulse_min_us: float
    pulse_max_us: float
    center_us: float = 1500.0

    def pulse_for(self, angle_deg: float) -> float:
        return clamp(self.center_us + (angle_deg - self.c) / self.m,
                     self.pulse_min_us, self.pulse_max_us)


def load_servo_cal(servo_cfg, base_dir: Path) -> Dict[str, ServoCal]:
    """Calibration per servo from config/servo_cal.json, else the config defaults (warned)."""
    default = ServoCal(servo_cfg.deg_per_us, 0.0, servo_cfg.pulse_min_us, servo_cfg.pulse_max_us,
                       servo_cfg.center_us)
    cal = {"pan": default, "tilt": default}
    path = Path(servo_cfg.calibration_file)
    if not path.is_absolute():
        path = base_dir / path
    if not path.exists():
        log.warning("no servo calibration file %s: using %.3f deg/us defaults", path,
                    servo_cfg.deg_per_us)
        return cal
    data = json.loads(path.read_text(encoding="utf-8"))
    for name in ("pan", "tilt"):
        if name in data:
            d = data[name]
            cal[name] = ServoCal(float(d["m"]), float(d["c"]),
                                 max(float(d["pulse_min_us"]), servo_cfg.pulse_min_us),
                                 min(float(d["pulse_max_us"]), servo_cfg.pulse_max_us),
                                 servo_cfg.center_us)
    return cal


class ServoBase:
    """Clamp, slew-limit and angle->pulse conversion shared by the real and sim servos.
    Subclasses implement ``_write_pulses(pan_us, tilt_us)``."""

    STEP_S = 0.02

    def __init__(self, clock, servo_cfg, cal: Dict[str, ServoCal]):
        self.clock = clock
        self.cfg = servo_cfg
        self.cal = cal
        self.limits_deg = (-servo_cfg.limit_deg, servo_cfg.limit_deg)
        self._cmd = (0.0, 0.0)
        self._pulses = (cal["pan"].pulse_for(0.0), cal["tilt"].pulse_for(0.0))

    def _write_pulses(self, pan_us: float, tilt_us: float) -> None:
        raise NotImplementedError

    def _set(self, pan_deg: float, tilt_deg: float) -> None:
        self._pulses = (self.cal["pan"].pulse_for(pan_deg), self.cal["tilt"].pulse_for(tilt_deg))
        self._write_pulses(*self._pulses)
        self._cmd = (pan_deg, tilt_deg)

    def move_to(self, pan_deg: float, tilt_deg: float, settle_s: float = 0.0) -> Tuple[float, float]:
        """Clamp to the soft limits, move in ~20 ms slew-limited steps, wait settle_s.
        Returns the clamped (pan, tilt) actually commanded."""
        lo, hi = self.limits_deg
        target = (clamp(pan_deg, lo, hi), clamp(tilt_deg, lo, hi))
        p0, t0 = self._cmd
        dist = max(abs(target[0] - p0), abs(target[1] - t0))
        steps = max(1, int(math.ceil(dist / (self.cfg.slew_deg_per_s * self.STEP_S))))
        for i in range(1, steps + 1):
            f = i / steps
            self._set(p0 + (target[0] - p0) * f, t0 + (target[1] - t0) * f)
            if i < steps:
                self.clock.sleep(self.STEP_S)
        if settle_s > 0:
            self.clock.sleep(settle_s)
        return target

    def write_pulse(self, axis: str, pulse_us: float) -> float:
        """Calibration only: write a raw pulse to one servo, clamped to its pulse range."""
        c = self.cal[axis]
        pulse = clamp(pulse_us, c.pulse_min_us, c.pulse_max_us)
        self._pulses = (pulse, self._pulses[1]) if axis == "pan" else (self._pulses[0], pulse)
        self._write_pulses(*self._pulses)
        angle = c.m * (pulse - c.center_us) + c.c
        self._cmd = (angle, self._cmd[1]) if axis == "pan" else (self._cmd[0], angle)
        return pulse

    def commanded(self) -> Tuple[float, float]:
        return self._cmd

    def pulses_us(self) -> Tuple[float, float]:
        return self._pulses
