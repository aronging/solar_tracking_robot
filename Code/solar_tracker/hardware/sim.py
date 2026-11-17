"""Lightweight simulated rig (spec 8.5): virtual clock, NOAA-reference sun, cosine panel,
noise, clouds, servo calibration error + backlash, yaw plant, lamp. Not a physics engine.

The simulator is the only place with ground truth: ``rig.sim`` (a SimWorld) exposes the
injected offsets and the true pointing error. One seeded random.Random drives everything.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from ..clock import SimClock
from ..config import CODE_DIR
from ..geometry import clamp, incidence_cos, wrap360
from ..solar.clearsky import attenuation
from ..solar.reference_noaa import noaa_azel
from .base import ImuCal, PanelReading, Rig, ServoBase, ServoCal, mean_std

PCA_STEP_US = 20000.0 / 4096.0          # PCA9685 resolution at 50 Hz


@dataclass
class SimParams:
    seed: int = 0
    start_utc: datetime = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
    true_az_offset_deg: float = 0.0     # injected mounting/heading error the learner must find
    true_el_offset_deg: float = 0.0
    heading0_true_deg: Optional[float] = None   # None = random start heading
    imu_bias_deg: float = 0.0
    imu_noise_deg: float = 0.3
    yaw_K_deg_s: float = 60.0           # yaw rate at u = 1
    yaw_deadband: float = 0.2
    yaw_tau_s: float = 0.3
    cal_gain: float = 1.0               # true servo angle = cal_gain * commanded + cal_zero
    cal_zero_pan_deg: float = 0.0
    cal_zero_tilt_deg: float = 0.0
    backlash_deg: float = 1.5
    k_sim_mA: float = 260.0
    diffuse_frac: float = 0.04
    noise_mA: float = 0.4
    clouds: List[Tuple[float, float, float]] = field(default_factory=list)  # (t0_s, t1_s, factor)
    lamp: Optional[Tuple[float, float]] = None   # (az_deg, el_deg): lamp mode instead of the sun
    lamp_mA: float = 200.0
    ambient_mA: float = 3.0
    sample_period_s: float = 0.02


class SimWorld:
    """Ground-truth state of the simulated robot and sky."""

    def __init__(self, cfg, p: SimParams):
        self.cfg, self.p = cfg, p
        self.rng = random.Random(p.seed)
        self.clock = SimClock(p.start_utc, self.step)
        self.heading_true = (p.heading0_true_deg if p.heading0_true_deg is not None
                             else self.rng.uniform(0.0, 360.0))
        self.yaw_rate = 0.0
        self.u = 0.0
        self.pan_true = 0.0             # servo output angles after gain/zero error + backlash
        self.tilt_true = 0.0
        self.lamp = p.lamp
        self.fail_panel = False         # tests set this to make the INA219 raise OSError
        self.turn_commands: List[Tuple[float, float]] = []   # (t_mono, u) for every non-zero u

    # -- dynamics -------------------------------------------------------------------
    def step(self, dt: float) -> None:
        p = self.p
        a = abs(self.u)
        drive = 0.0 if a <= p.yaw_deadband else math.copysign(
            (a - p.yaw_deadband) / (1.0 - p.yaw_deadband), self.u)
        self.yaw_rate += (p.yaw_K_deg_s * drive - self.yaw_rate) * min(1.0, dt / p.yaw_tau_s)
        self.heading_true = wrap360(self.heading_true + self.yaw_rate * dt)

    def _backlash(self, actual: float, target: float) -> float:
        half = 0.5 * self.p.backlash_deg
        if target > actual + half:
            return target - half
        if target < actual - half:
            return target + half
        return actual

    def servo_pulses(self, pan_us: float, tilt_us: float) -> None:
        s = self.cfg.servo

        def angle(pulse: float, zero: float) -> float:
            q = round(pulse / PCA_STEP_US) * PCA_STEP_US
            return self.p.cal_gain * (q - s.center_us) * s.deg_per_us + zero

        self.pan_true = self._backlash(self.pan_true, angle(pan_us, self.p.cal_zero_pan_deg))
        self.tilt_true = self._backlash(self.tilt_true, angle(tilt_us, self.p.cal_zero_tilt_deg))

    # -- truth ----------------------------------------------------------------------
    def normal(self) -> Tuple[float, float]:
        """True panel normal (az_deg, el_deg)."""
        s = self.cfg.servo
        return (wrap360(self.heading_true + self.p.true_az_offset_deg + s.pan_sign * self.pan_true),
                self.p.true_el_offset_deg + s.tilt_sign * self.tilt_true)

    def source(self) -> Tuple[float, float]:
        """True direction of the light source (lamp or sun)."""
        if self.lamp is not None:
            return self.lamp
        az, el, _ = noaa_azel(self.clock.now_utc(), self.cfg.site.lat_deg, self.cfg.site.lon_deg)
        return az, el

    def cos_incidence(self) -> float:
        (sa, se), (na, ne) = self.source(), self.normal()
        return incidence_cos(sa, se, na, ne)

    def pointing_error_deg(self) -> float:
        """True angle between the panel normal and the light source."""
        return math.degrees(math.acos(clamp(self.cos_incidence(), -1.0, 1.0)))

    def cloud_factor(self) -> float:
        t = self.clock.monotonic()
        f = 1.0
        for t0, t1, factor in self.p.clouds:
            if t0 <= t < t1:
                f = min(f, factor)
        return f

    def isc_true_mA(self) -> float:
        cos_i = max(0.0, self.cos_incidence())
        if self.lamp is not None:
            return self.p.lamp_mA * cos_i + self.p.ambient_mA
        i_n = self.p.k_sim_mA * attenuation(self.source()[1])
        return (i_n * cos_i + self.p.diffuse_frac * i_n) * self.cloud_factor()

    def move_lamp(self, az_deg: float, el_deg: float) -> None:
        self.lamp = (az_deg, el_deg)


class SimServos(ServoBase):
    def __init__(self, world: SimWorld, cal):
        super().__init__(world.clock, world.cfg.servo, cal)
        self.world = world

    def _write_pulses(self, pan_us: float, tilt_us: float) -> None:
        self.world.servo_pulses(pan_us, tilt_us)


class SimPanel:
    def __init__(self, world: SimWorld):
        self.w = world

    def read(self, n_samples: int = 8) -> PanelReading:
        w = self.w
        if w.fail_panel:
            raise OSError("simulated I2C failure (INA219)")
        samples = []
        for _ in range(n_samples):
            w.clock.sleep(w.p.sample_period_s)
            raw = w.isc_true_mA() + w.rng.gauss(0.0, w.p.noise_mA)
            samples.append(clamp(round(raw, 1), 0.0, 400.0))      # 0.1 mA per count
        mean, std = mean_std(samples)
        mean -= w.cfg.panel.zero_offset_mA
        return PanelReading(mean, std, n_samples, 0.02,
                            any(s > w.cfg.hardware.overrange_mA for s in samples))


class SimImu:
    def __init__(self, world: SimWorld):
        self.w = world

    def heading_deg(self) -> float:
        w = self.w
        return wrap360(w.heading_true - w.cfg.site.declination_deg + w.p.imu_bias_deg
                       + w.rng.gauss(0.0, w.p.imu_noise_deg))

    def calibration(self) -> ImuCal:
        return ImuCal(3, 3, 3, 3)


class SimDrive:
    def __init__(self, world: SimWorld):
        self.w = world

    def set_turn(self, u: float) -> None:
        d = self.w.cfg.drive
        u = clamp(u, -d.max_duty, d.max_duty) * d.turn_sign
        self.w.u = u
        if u != 0.0:
            self.w.turn_commands.append((self.w.clock.monotonic(), u))

    def stop(self) -> None:
        self.w.u = 0.0


def make_sim_rig(cfg, params: Optional[SimParams] = None) -> Rig:
    """Simulated Rig. The servo HAL uses the uncalibrated default map, so the injected
    cal_gain / cal_zero errors are real errors the tracker has to live with."""
    world = SimWorld(cfg, params or SimParams())
    s = cfg.servo
    default = ServoCal(s.deg_per_us, 0.0, s.pulse_min_us, s.pulse_max_us, s.center_us)
    info = {"backend": "sim", "i2c_scan": ["0x40", "0x70"], "pca9685_hz": 50.0,
            "ntp_synced": True, "seed": world.p.seed, "code_dir": str(CODE_DIR)}
    return Rig(world.clock, SimServos(world, {"pan": default, "tilt": default}), SimPanel(world),
               SimImu(world), SimDrive(world), info, world)
