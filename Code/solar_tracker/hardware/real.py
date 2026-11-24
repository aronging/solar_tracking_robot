"""Real Raspberry Pi backend (spec 8.2). Importable anywhere: every hardware library is
imported inside make_real_rig(), never at module level.

The bus is opened with the lab scripts in Code/lab/ (put on sys.path in make_real_rig):
- lab/motor_servo_pwm.py `_PCA9685()` opens the PCA9685 HAT (0x40) and sets it to 100 Hz;
  the servo pulse period is computed from the frequency read back. It is opened FIRST
  (its init disables the PCA all-call address 0x70, which the mux uses);
- lab/sensor_module.py `CreateMuxI2C(channel)` gives each mux (0x70) channel for the
  INA219 and BNO055; the wheels are two lab `PWM_Motor(fwd, rv)` objects;
- every bus access happens under one RLock (BUS_LOCK);
- unknown channels are never guessed: a None config value raises ConfigError.

NOT YET RUN ON THE ROBOT: written against the Adafruit CircuitPython APIs; verify with
`python -m solar_tracker preflight` (README, first power-up checklist).
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from typing import Optional

from ..clock import SystemClock
from ..config import CODE_DIR, REQUIRED_DRIVE, REQUIRED_REAL, require
from ..geometry import clamp, wrap360
from .base import ImuCal, PanelReading, Rig, ServoBase, load_servo_cal, mean_std

log = logging.getLogger("solar_tracker")
BUS_LOCK = threading.RLock()       # import this lock into any lab thread that touches the mux


def ntp_synced() -> Optional[bool]:
    """True/False from timedatectl (fallback chronyc); None if neither can tell."""
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip() in ("yes", "no"):
            return out.stdout.strip() == "yes"
        out = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return "Leap status     : Normal" in out.stdout
    except Exception:
        pass
    return None


class RealServos(ServoBase):
    def __init__(self, clock, servo_cfg, cal, pca, ch_pan: int, ch_tilt: int, period_us: float):
        super().__init__(clock, servo_cfg, cal)
        self._pan, self._tilt = pca.channels[ch_pan], pca.channels[ch_tilt]
        self._period_us = period_us

    def _duty(self, pulse_us: float) -> int:
        return int(round(clamp(pulse_us / self._period_us, 0.0, 1.0) * 65535))

    def _write_pulses(self, pan_us: float, tilt_us: float) -> None:
        with BUS_LOCK:
            self._pan.duty_cycle = self._duty(pan_us)
            self._tilt.duty_cycle = self._duty(tilt_us)

    def release(self) -> None:
        with BUS_LOCK:
            self._pan.duty_cycle = 0
            self._tilt.duty_cycle = 0


class RealPanel:
    """INA219 across the shorted panel: 16 V / 400 mA range, 0.1 mA per count."""

    def __init__(self, ina, cfg, sample_period_s: float):
        self.ina, self.cfg, self.sample_period_s = ina, cfg, sample_period_s

    def read(self, n_samples: int = 8) -> PanelReading:
        samples = []
        with BUS_LOCK:
            for i in range(n_samples):
                if i:
                    time.sleep(self.sample_period_s)        # wait for a fresh conversion
                samples.append(float(self.ina.current))
            bus_v = float(self.ina.bus_voltage)
        mean, std = mean_std(samples)
        return PanelReading(mean - self.cfg.panel.zero_offset_mA, std, n_samples, bus_v,
                            any(abs(s) > self.cfg.hardware.overrange_mA for s in samples))


class RealImu:
    """BNO055 in NDOF (fusion) mode; heading = Euler angle 0, magnetic, [0, 360)."""

    def __init__(self, bno):
        self.bno = bno

    def heading_deg(self) -> float:
        for _ in range(3):                                  # None until the fusion settles
            with BUS_LOCK:
                euler = self.bno.euler
            if euler is not None and euler[0] is not None:
                return wrap360(float(euler[0]))
            time.sleep(0.05)
        raise RuntimeError("BNO055 returned no heading")

    def calibration(self) -> ImuCal:
        with BUS_LOCK:
            s, g, a, m = self.bno.calibration_status
        return ImuCal(int(s), int(g), int(a), int(m))


class RealDrive:
    """Turn-in-place wheel drive through two lab PWM_Motor objects (FWD/RV channel pair,
    duty -100..100 %). The motors are created on the first set_turn, after
    drive.left_motor_channels / right_motor_channels are checked, so a servo-only session
    never touches a wheel channel. ``motor_factory(fwd, rv)`` is the lab PWM_Motor class
    on the robot and a fake in the tests. Like the lab's test_motor.py, each PWM_Motor
    re-opens the PCA9685 at 100 Hz, so the servo outputs blip for a few ms on the first turn."""

    def __init__(self, cfg, motor_factory):
        self.cfg, self._factory = cfg, motor_factory
        self._motors = None                 # (left, right) once the wheels were driven

    def set_turn(self, u: float) -> None:
        d = self.cfg.drive
        require(self.cfg, *REQUIRED_DRIVE)
        u = clamp(u, -d.max_duty, d.max_duty) * d.turn_sign
        with BUS_LOCK:
            if self._motors is None:
                self._motors = (self._factory(*d.left_motor_channels),
                                self._factory(*d.right_motor_channels))
            left, right = self._motors      # clockwise: left wheel forward, right wheel back
            left.set_motor_duty(100.0 * u * d.left_sign)
            right.set_motor_duty(-100.0 * u * d.right_sign)

    def stop(self) -> None:
        """Idempotent; retries once per motor; never raises. No-op if never driven."""
        for motor in self._motors or ():
            for _ in range(2):
                try:
                    with BUS_LOCK:
                        motor.stop_motor()
                    break
                except Exception:
                    time.sleep(0.02)


def _versions() -> dict:
    out = {}
    try:
        from importlib import metadata
        for pkg in ("adafruit-blinka", "adafruit-circuitpython-pca9685",
                    "adafruit-circuitpython-tca9548a", "adafruit-circuitpython-ina219",
                    "adafruit-circuitpython-bno055"):
            try:
                out[pkg] = metadata.version(pkg)
            except Exception:
                out[pkg] = None
    except Exception:
        pass
    return out


def make_real_rig(cfg) -> Rig:
    """Open the hardware in the mandated order and return the Rig. Raises ConfigError for
    a missing required value."""
    require(cfg, *REQUIRED_REAL)
    h = cfg.hardware
    lab = str(CODE_DIR / "lab")
    if lab not in sys.path:
        sys.path.append(lab)
    from motor_servo_pwm import _PCA9685, PWM_Motor   # lazy: Raspberry Pi only (lab scripts)
    from sensor_module import CreateMuxI2C
    from adafruit_ina219 import INA219
    import adafruit_bno055

    with BUS_LOCK:
        pca = _PCA9685().pca                       # FIRST: 0x40 @ 100 Hz, disables all-call (0x70)
        hz = float(pca.frequency)
    period_us = 1.0e6 / hz
    i2c = pca.i2c_device.i2c

    scan = []
    try:
        if i2c.try_lock():
            scan = ["0x%02x" % a for a in i2c.scan()]
            i2c.unlock()
    except Exception as exc:
        log.warning("i2c scan failed: %r", exc)

    with BUS_LOCK:
        ina = INA219(CreateMuxI2C(h.mux_channel_panel), addr=h.ina219_address)
        ina.set_calibration_16V_400mA()
        sample_period_s = 0.002
        try:                                       # 12-bit, 128-sample hardware averaging (~68 ms)
            from adafruit_ina219 import ADCResolution
            ina.bus_adc_resolution = ADCResolution.ADCRES_12BIT_128S
            ina.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_128S
            sample_period_s = 0.07
        except Exception as exc:
            log.warning("INA219 hardware averaging not available (%r); averaging in software", exc)
        bno = adafruit_bno055.BNO055_I2C(CreateMuxI2C(h.mux_channel_imu), address=h.imu_address)

    clock = SystemClock()
    servos = RealServos(clock, cfg.servo, load_servo_cal(cfg.servo, CODE_DIR), pca,
                        h.servo_channel_pan, h.servo_channel_tilt, period_us)
    info = {"backend": "real", "i2c_scan": scan, "pca9685_hz": hz, "ntp_synced": ntp_synced(),
            "versions": _versions(), "code_dir": str(CODE_DIR)}

    def closer() -> None:
        servos.release()
        i2c.deinit()

    return Rig(clock, servos, RealPanel(ina, cfg, sample_period_s), RealImu(bno),
               RealDrive(cfg, PWM_Motor), info, None, closer)
