"""Real Raspberry Pi backend (spec 8.2). Importable anywhere: every hardware library is
imported inside make_real_rig(), never at module level.

Bus rules implemented here (spec 3.2):
- order: I2C bus -> PCA9685 -> mux; the mux is never re-addressed;
- the PCA9685 frequency is read back and must be ~50 Hz; it is NOT changed unless
  hardware.allow_set_pca9685_hz is true (changing it alters wheel-motor behaviour);
- every mux-using read happens under one RLock (BUS_LOCK);
- unknown channels are never guessed: a None config value raises ConfigError.

NOT YET RUN ON THE ROBOT: written against the Adafruit CircuitPython APIs; verify with
`python -m solar_tracker preflight` (README, first power-up checklist).
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from typing import Optional

from ..clock import SystemClock
from ..config import CODE_DIR, REQUIRED_DRIVE, REQUIRED_REAL, ConfigError, require
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
    """Turn-in-place wheel drive. The wheel-driver wiring is UNKNOWN (spec 17.3), so
    nothing is written to any channel until drive.left_channel, drive.right_channel and
    drive.direction_scheme are set. Implemented scheme:

      "rc_pulse": each driver takes an RC-style pulse, 1500 us = stop, +-500 us = full.

    If the lab's test_motor.py drives the motors differently, add that scheme here
    (copy its convention; do not guess).
    """

    def __init__(self, pca, cfg, period_us: float):
        self.pca, self.cfg, self.period_us = pca, cfg, period_us
        self._armed = False

    def _write(self, left: float, right: float) -> None:
        d = self.cfg.drive
        with BUS_LOCK:
            for ch, v in ((d.left_channel, left * d.left_sign), (d.right_channel, right * d.right_sign)):
                pulse = 1500.0 + 500.0 * clamp(v, -d.max_duty, d.max_duty)
                self.pca.channels[ch].duty_cycle = int(round(pulse / self.period_us * 65535))

    def set_turn(self, u: float) -> None:
        d = self.cfg.drive
        require(self.cfg, *REQUIRED_DRIVE)
        if d.direction_scheme != "rc_pulse":
            raise ConfigError("drive.direction_scheme=%r is not implemented; only 'rc_pulse' is. "
                              "Add the lab's scheme to hardware/real.py:RealDrive"
                              % d.direction_scheme)
        self._armed = True
        u = clamp(u, -d.max_duty, d.max_duty) * d.turn_sign
        self._write(u, -u)                  # clockwise: left wheel forward, right wheel back

    def stop(self) -> None:
        """Idempotent; retries once; never raises. No-op if the wheels were never driven."""
        if not self._armed:
            return
        for _ in range(2):
            try:
                self._write(0.0, 0.0)
                return
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
    a missing required value or a PCA9685 that is not at ~50 Hz."""
    require(cfg, *REQUIRED_REAL)
    h = cfg.hardware
    import board                                   # lazy: Raspberry Pi only
    import busio
    import adafruit_tca9548a
    from adafruit_pca9685 import PCA9685
    from adafruit_ina219 import INA219
    import adafruit_bno055

    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=h.pca9685_address)  # FIRST: its init disables all-call (0x70)
    hz = float(pca.frequency)
    if abs(hz - h.pca9685_expected_hz) > 0.1 * h.pca9685_expected_hz:
        if not h.allow_set_pca9685_hz:
            raise ConfigError(
                "PCA9685 frequency reads %.1f Hz, expected ~%.0f Hz. Not changing it (it is shared "
                "with the wheel motors). After a power cycle run the lab's motor_servo_pwm setup "
                "first, or set hardware.allow_set_pca9685_hz=true if you accept changing it."
                % (hz, h.pca9685_expected_hz))
        pca.frequency = h.pca9685_expected_hz
        hz = float(pca.frequency)
    period_us = 1.0e6 / hz
    mux = adafruit_tca9548a.TCA9548A(i2c, address=h.mux_address)

    scan = []
    try:
        if i2c.try_lock():
            scan = ["0x%02x" % a for a in i2c.scan()]
            i2c.unlock()
    except Exception as exc:
        log.warning("i2c scan failed: %r", exc)

    with BUS_LOCK:
        ina = INA219(mux[h.mux_channel_panel], addr=h.ina219_address)
        ina.set_calibration_16V_400mA()
        sample_period_s = 0.002
        try:                                       # 12-bit, 128-sample hardware averaging (~68 ms)
            from adafruit_ina219 import ADCResolution
            ina.bus_adc_resolution = ADCResolution.ADCRES_12BIT_128S
            ina.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_128S
            sample_period_s = 0.07
        except Exception as exc:
            log.warning("INA219 hardware averaging not available (%r); averaging in software", exc)
        bno = adafruit_bno055.BNO055_I2C(mux[h.mux_channel_imu], address=h.imu_address)

    clock = SystemClock()
    servos = RealServos(clock, cfg.servo, load_servo_cal(cfg.servo, CODE_DIR), pca,
                        h.servo_channel_pan, h.servo_channel_tilt, period_us)
    info = {"backend": "real", "i2c_scan": scan, "pca9685_hz": hz, "ntp_synced": ntp_synced(),
            "versions": _versions(), "code_dir": str(CODE_DIR)}

    def closer() -> None:
        servos.release()
        i2c.deinit()

    return Rig(clock, servos, RealPanel(ina, cfg, sample_period_s), RealImu(bno),
               RealDrive(pca, cfg, period_us), info, None, closer)
