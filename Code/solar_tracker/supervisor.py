"""Supervisor: the session state machine, scheduling and safety (spec sections 6 and 9).

PREFLIGHT -> COARSE_ALIGN -> ACQUIRE -> TRACK <-> HOLD -> PARK -> DONE, FAULT from anywhere.
Algorithms get callbacks; this module is the only place that wires them to the HAL.
Nothing here uses real time directly: everything goes through rig.clock.
"""
from __future__ import annotations

import math
import platform
import random
import signal
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .clock import SystemClock
from .config import REQUIRED_DRIVE, Config, ConfigError, require
from .control.acquire import AcquireResult, acquire_axis
from .control.heading import circular_mean_deg, coarse_turn
from .control.offsets import OffsetEstimator
from .control.pid import PID
from .control.refine import Gates, evaluate_scan, run_scan
from .geometry import angdiff, clamp, incidence_cos, pointing_to_servo, servo_to_pointing, wrap360
from .hardware.base import HardwareError, PanelReading, Rig
from .logging_ import SessionLogger, git_commit
from .solar.clearsky import clear_isc_mA, cloud_ratio, estimate_k_mA
from .solar.position import SunPosition, sun_position

BOOTSTRAP_SIGMA_DEG = 1.0      # weight given to an acquire-derived offset sample
MIN_COARSE_STEP_DEG = 7.5      # narrower coarse spacing differs by less than the noise
SIGMA_FLOOR_DEG = 0.2          # floor on a scan's sigma so one lucky fit cannot dominate
BOOTSTRAP_FAULT_MSG = ("offset %s = %.1f deg exceeds pointing.max_bootstrap_offset_deg = %.1f. "
                       "Is the panel facing the sun? Is the clock right? Is the heading sane?")


class Fault(Exception):
    """Unrecoverable condition: park, stop wheels, close logs, exit non-zero."""


class StopSession(Exception):
    """Operator stop (SIGINT/SIGTERM) or end of the requested duration: clean PARK."""


class _ScanAbort(Exception):
    """Cloud detected in the middle of a scan or fixed check."""


@dataclass
class Options:
    mode: str = "sun"                    # "sun" | "lamp"
    skip_turn: bool = False
    robot_on_ground: bool = False
    bench: bool = False
    ack_clock: bool = False
    k_mA: Optional[float] = None
    duration_s: Optional[float] = None
    target_heading_deg: Optional[float] = None
    command: str = "track"
    argv: Optional[List[str]] = None


class Watchdog:
    """Real-time thread: calls on_fire() once if kick() is not called for timeout_s."""

    def __init__(self, timeout_s: float, on_fire: Callable[[], None]):
        self.timeout_s, self.on_fire = timeout_s, on_fire
        self._last = time.monotonic()
        self._stop = threading.Event()
        self.fired = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def kick(self) -> None:
        self._last = time.monotonic()

    def _run(self) -> None:
        while not self._stop.wait(self.timeout_s / 4.0):
            if time.monotonic() - self._last > self.timeout_s:
                self.fired = True
                self.on_fire()
                return

    def cancel(self) -> None:
        self._stop.set()


class Supervisor:
    def __init__(self, cfg: Config, rig: Rig, log: SessionLogger, opts: Optional[Options] = None,
                 rng: Optional[random.Random] = None,
                 on_tick: Optional[Callable[["Supervisor"], None]] = None):
        self.cfg, self.rig, self.log = cfg, rig, log
        self.clock = rig.clock
        self.opts = opts or Options()
        self.rng = rng or random.Random()
        self.on_tick = on_tick                      # test/demo hook, called once per tick
        self.state = "INIT"
        self.stop_requested = False
        self.exit_reason = ""
        self.heading_true_deg = 0.0                 # session heading, fixed after COARSE_ALIGN
        r = cfg.refine
        self.az = OffsetEstimator(cfg.pointing.az_offset_init_deg, r.offset_forget, SIGMA_FLOOR_DEG)
        self.el = OffsetEstimator(cfg.pointing.el_offset_init_deg, r.offset_forget, SIGMA_FLOOR_DEG)
        self.k_mA = self.opts.k_mA or cfg.panel.k_clear_mA or 0.0
        self.flags: set = set()
        self.imu_cal = None
        self.coarse_align_failed = False
        self._hw_errors: deque = deque()
        self._scan_id = 0
        self._acq_id = 0
        self._spread_deg = r.spread_deg
        self._drift_count = {"pan": 0, "tilt": 0}
        self._rejects = 0
        self._limit_since: Optional[float] = None
        self._last_reading: Optional[PanelReading] = None
        self.session: Dict[str, Any] = {}

    # ------------------------------------------------------------------ plumbing
    def set_state(self, state: str, **fields: Any) -> None:
        if state != self.state:
            self.log.event("state", frm=self.state, to=state, **fields)
            self.state = state

    def check_stop(self) -> None:
        if self.stop_requested:
            raise StopSession("stop requested")

    def _retry(self, fn: Callable[[], Any], what: str) -> Any:
        """I2C error policy: 3 tries, then HardwareError; 3 HardwareErrors in 60 s -> Fault."""
        last: Optional[BaseException] = None
        for _ in range(3):
            try:
                return fn()
            except (OSError, RuntimeError) as exc:
                last = exc
                self.clock.sleep(0.05)
        now = self.clock.monotonic()
        self._hw_errors.append(now)
        while self._hw_errors and now - self._hw_errors[0] > 60.0:
            self._hw_errors.popleft()
        self.log.event("hardware_error", "ERROR", what=what, error=repr(last),
                       recent=len(self._hw_errors))
        if len(self._hw_errors) >= 3:
            raise Fault("3 hardware errors within 60 s (last: %s: %r)" % (what, last))
        raise HardwareError("%s failed after 3 tries: %r" % (what, last))

    def read_panel(self, n: Optional[int] = None) -> PanelReading:
        n = n or self.cfg.panel.n_samples_default
        return self._retry(lambda: self.rig.panel.read(n), "panel.read")

    def read_heading_true(self) -> float:
        mag = self._retry(self.rig.imu.heading_deg, "imu.heading")
        return wrap360(mag + self.cfg.site.declination_deg)

    def move(self, pan_deg: float, tilt_deg: float, settle: bool = True) -> Tuple[float, float]:
        s = self.cfg.servo.settle_s if settle else 0.0
        return self._retry(lambda: self.rig.servos.move_to(pan_deg, tilt_deg, s), "servos.move_to")

    def sun(self) -> SunPosition:
        return sun_position(self.clock.now_utc(), self.cfg.site.lat_deg, self.cfg.site.lon_deg)

    def _servo_args(self) -> Tuple[float, float, float, int, int]:
        return (self.heading_true_deg, self.az.value_deg, self.el.value_deg,
                self.cfg.servo.pan_sign, self.cfg.servo.tilt_sign)

    def predicted_cmd(self, az_deg: float, el_deg: float) -> Tuple[float, float]:
        """Unclamped servo command that points the normal at (az, el) with the current offsets."""
        return pointing_to_servo(az_deg, el_deg, *self._servo_args())

    def _clamped(self, pan: float, tilt: float) -> Tuple[float, float]:
        lo, hi = self.rig.servos.limits_deg
        return clamp(pan, lo, hi), clamp(tilt, lo, hi)

    def point_at_sun(self, sun: Optional[SunPosition] = None, settle: bool = False) -> None:
        """Re-point by prediction; maintain LIMIT_PAN / LIMIT_TILT flags."""
        sun = sun or self.sun()
        pan, tilt = self.predicted_cmd(sun.az_deg, sun.el_deg)
        cp, ct = self.move(pan, tilt, settle)
        for flag, hit in (("LIMIT_PAN", abs(cp - pan) > 1e-9), ("LIMIT_TILT", abs(ct - tilt) > 1e-9)):
            (self.flags.add if hit else self.flags.discard)(flag)
        now = self.clock.monotonic()
        if "LIMIT_PAN" in self.flags:
            if self._limit_since is None:
                self._limit_since = now
            elif now - self._limit_since > self.cfg.track.limit_replan_s:
                self.log.event("limit_replan", "WARNING",
                               hint="pan at its limit; a new coarse turn would re-centre the range")
                self._limit_since = now
        else:
            self._limit_since = None

    def cos_i_pred(self, sun: SunPosition) -> float:
        """Predicted incidence cosine at the current commanded pointing."""
        n_az, n_el = servo_to_pointing(*self.rig.servos.commanded(), *self._servo_args())
        return incidence_cos(sun.az_deg, sun.el_deg, n_az, n_el)

    # ------------------------------------------------------------------ run wrapper
    def run(self, body: Callable[[], None]) -> int:
        """Run one command body with signal handling, fault handling and cleanup."""
        code = 0
        old: Dict[int, Any] = {}

        def on_signal(signum, frame):
            self.stop_requested = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                old[sig] = signal.signal(sig, on_signal)
            except (ValueError, OSError):            # not the main thread
                pass
        self.session = {
            "start_utc": self.clock.now_utc().isoformat(), "command": self.opts.command,
            "argv": self.opts.argv if self.opts.argv is not None else sys.argv,
            "git_commit": git_commit(self.rig.info.get("code_dir")),
            "python": platform.python_version(), "platform": platform.platform(),
            "config": self.cfg.as_dict(), "rig": {k: v for k, v in self.rig.info.items()},
        }
        try:
            body()
            self.exit_reason = self.exit_reason or "done"
        except StopSession as exc:
            self.exit_reason = str(exc)
            self._safe_park()
        except BaseException as exc:                 # Fault, bugs, KeyboardInterrupt
            code = 1
            self.exit_reason = "FAULT: %s" % exc
            self.state = "FAULT"
            self.log.event("fault", "ERROR", error=repr(exc), traceback=traceback.format_exc())
            self._safe_park()
            self.state = "FAULT"                     # parked, but the session ended in FAULT
        finally:
            self.rig.drive.stop()
            self.session.update({
                "end_utc": self.clock.now_utc().isoformat(), "exit_reason": self.exit_reason,
                "exit_code": code, "k_clear_mA": self.k_mA,
                "heading_true_deg": self.heading_true_deg,
                "coarse_align_failed": self.coarse_align_failed,
                "final_offsets": {"az_offset_deg": self.az.value_deg, "az_se_deg": self.az.se_deg,
                                  "el_offset_deg": self.el.value_deg, "el_se_deg": self.el.se_deg,
                                  "n_az": len(self.az.values), "n_el": len(self.el.values)},
            })
            if self.rig.sim is not None:
                p = self.rig.sim.p
                self.session["sim_truth"] = {"true_az_offset_deg": p.true_az_offset_deg,
                                             "true_el_offset_deg": p.true_el_offset_deg,
                                             "seed": p.seed}
            try:
                self.log.write_session(self.session)
            finally:
                self.rig.close()
                self.log.close()
                for sig, handler in old.items():
                    signal.signal(sig, handler)
        return code

    def _safe_park(self) -> None:
        try:
            self.park()
        except Exception as exc:
            self.log.event("park_failed", "ERROR", error=repr(exc))

    def park(self) -> None:
        self.set_state("PARK")
        self.rig.drive.stop()
        p = self.cfg.pointing
        self.rig.servos.move_to(p.park_pan_deg, p.park_tilt_deg, 0.0)
        self.set_state("DONE")

    # ------------------------------------------------------------------ preflight (6.0)
    def preflight(self) -> None:
        self.set_state("PREFLIGHT")
        c, info = self.cfg, self.rig.info
        self.log.event("i2c", scan=info.get("i2c_scan"), pca9685_hz=info.get("pca9685_hz"))
        r = self.read_panel()
        self.log.event("panel", isc_mA=r.isc_mA, isc_std_mA=r.isc_std_mA, bus_V=r.bus_V)
        if r.isc_mA < -1.0:
            self.log.event("panel_warning", "WARNING", why="negative current: panel polarity reversed?")
        if r.bus_V > 1.0:
            self.log.event("panel_warning", "WARNING", why="bus voltage > 1 V: panel not shorted?")
        if r.overrange:
            self.log.event("panel_warning", "WARNING", why="current above overrange_mA")
        self.imu_cal = self._retry(self.rig.imu.calibration, "imu.calibration")
        heading = self.read_heading_true()
        self.log.event("imu", heading_true_deg=heading, cal_sys=self.imu_cal.sys,
                       cal_gyro=self.imu_cal.gyro, cal_accel=self.imu_cal.accel,
                       cal_mag=self.imu_cal.mag)
        if self.imu_cal.mag < c.align.imu_mag_cal_min:
            self.log.event("imu_warning", "WARNING",
                           why="magnetometer calibration %d < %d: move the robot through "
                               "figure-eights and hold it still on each face"
                               % (self.imu_cal.mag, c.align.imu_mag_cal_min))
        self.session["imu_cal_start"] = vars(self.imu_cal) if hasattr(self.imu_cal, "__dict__") \
            else {"sys": self.imu_cal.sys, "gyro": self.imu_cal.gyro, "accel": self.imu_cal.accel,
                  "mag": self.imu_cal.mag}
        synced = info.get("ntp_synced")
        self.log.event("clock", utc=self.clock.now_utc().isoformat(), ntp_synced=synced)
        if self.opts.mode == "sun" and self.opts.command in ("track", "acquire") \
                and not synced and not self.opts.ack_clock:
            raise Fault("system clock is not NTP-synchronised (1 min of clock error = 0.25 deg). "
                        "Check `date -u` against a phone and pass --ack-clock.")
        sun = self.sun()
        self.log.event("sun", az_deg=sun.az_deg, el_deg=sun.el_deg, decl_deg=sun.decl_deg,
                       kepler_iterations=sun.kepler_iterations,
                       below_min_elevation=sun.el_deg < c.pointing.min_elevation_deg)
        for pan, tilt in ((20, 0), (-20, 0), (0, 0), (0, 20), (0, -20), (0, 0)):
            self.check_stop()
            self.move(pan, tilt)
        self.log.event("preflight_ok")

    # ------------------------------------------------------------------ coarse align (6.2)
    def coarse_align(self) -> None:
        c, o = self.cfg, self.opts
        self.set_state("COARSE_ALIGN")
        sim = self.rig.sim is not None
        if o.skip_turn:
            self.heading_true_deg = circular_mean_deg([self.read_heading_true() for _ in range(20)])
            self.log.event("coarse_align_skipped", heading_true_deg=self.heading_true_deg)
            return
        if not (sim or o.robot_on_ground or o.bench):
            raise Fault("refusing to drive the wheels: pass --robot-on-ground (robot on the floor), "
                        "--bench (wheels disabled, virtual plant) or --skip-turn")
        if not (sim or o.bench):
            require(c, *REQUIRED_DRIVE)
        cal = self._retry(self.rig.imu.calibration, "imu.calibration")
        if cal.mag < c.align.imu_mag_cal_min:
            self.coarse_align_failed = True
            self.heading_true_deg = circular_mean_deg([self.read_heading_true() for _ in range(20)])
            self.log.event("coarse_align_failed", "WARNING", why="magnetometer not calibrated",
                           heading_true_deg=self.heading_true_deg)
            return
        target = wrap360((o.target_heading_deg if o.target_heading_deg is not None
                          else c.align.target_heading_true_deg) - c.pointing.az_offset_init_deg)
        a = c.align
        pid = PID(a.kp, a.ki, a.kd, a.integral_mode, a.d_filter_tau_s, u_limit=1.0, angular=True)
        read, set_turn, stop = self.read_heading_true, self.rig.drive.set_turn, self.rig.drive.stop
        if o.bench and not sim:                      # wheels disabled: PID drives a virtual plant
            virt = {"h": self.read_heading_true()}
            period = 1.0 / a.loop_hz

            def set_turn(u: float) -> None:          # noqa: F811
                virt["h"] = wrap360(virt["h"] + 60.0 * clamp(u, -c.drive.max_duty, c.drive.max_duty) * period)

            read, stop = (lambda: virt["h"]), (lambda: None)
        dog = Watchdog(1.0, self.rig.drive.stop) if isinstance(self.clock, SystemClock) else None

        def on_sample(row: Dict[str, object]) -> None:
            self.log.row("turn.csv", row)
            if dog:
                dog.kick()

        try:
            res = coarse_turn(read, set_turn, stop, self.clock, target, pid, a.tol_deg, a.hold_s,
                              a.max_turn_s, a.loop_hz, c.drive.min_turn_duty, 1.0, on_sample,
                              lambda: self.stop_requested or bool(dog and dog.fired))
        finally:
            self.rig.drive.stop()
            if dog:
                dog.cancel()
        self.check_stop()
        if dog and dog.fired:
            raise Fault("watchdog: coarse-turn loop stalled; wheels stopped")
        self.heading_true_deg = (circular_mean_deg([self.read_heading_true() for _ in range(20)])
                                 if o.bench and not sim else res.final_heading_deg)
        self.coarse_align_failed = not res.success
        self.log.event("coarse_align", "INFO" if res.success else "WARNING", success=res.success,
                       reason=res.reason, target_deg=target, heading_true_deg=self.heading_true_deg,
                       duration_s=res.duration_s, integral_mode=a.integral_mode)

    # ------------------------------------------------------------------ acquire (6.3)
    def _acquire_passes(self, pan0: float, tilt0: float, half_width: float
                        ) -> Tuple[Optional[float], Optional[float], float]:
        """pan search, tilt search, then n_passes-1 more pan searches. Returns the peak
        (pan, tilt, isc) or (None, None, best) on no signal."""
        a = self.cfg.acquire
        limits = self.rig.servos.limits_deg
        pan, tilt = self._clamped(pan0, tilt0)
        self._acq_id += 1
        f_best = 0.0
        plan = [("pan", half_width), ("tilt", half_width)] + \
               [("pan", min(half_width, a.later_half_width_deg))] * (a.n_passes - 1)
        for axis, hw in plan:
            def f(x: float, axis=axis) -> float:
                self.check_stop()
                self.move(x if axis == "pan" else pan, tilt if axis == "pan" else x)
                return self.read_panel(a.samples_per_point).isc_mA

            res: AcquireResult = acquire_axis(f, pan if axis == "pan" else tilt, hw, limits,
                                              a.n_coarse, a.tol_deg, a.max_evals,
                                              self.cfg.panel.min_signal_mA, MIN_COARSE_STEP_DEG)
            t = self.clock.now_utc()
            for h in res.history:
                row = {"acq_id": self._acq_id, "t_utc": t, "axis": axis, "phase": h["phase"],
                       "iter": h["iter"], "x_deg": h["x"], "f_mA": h["f"],
                       "interval_width_deg": h["width"]}
                if h["phase"] == "result":
                    row.update(x_golden_deg=res.x_golden, x_parabolic_deg=res.x_parabolic,
                               x_best_deg=res.x_best)
                self.log.row("acquire.csv", row)
            if res.no_signal:
                self.log.event("acquire_no_signal", "WARNING", axis=axis, best_mA=res.f_best)
                return None, None, res.f_best
            if res.edge_peak:
                self.log.event("acquire_edge_peak", "WARNING", axis=axis, x_deg=res.x_best)
            if axis == "pan":
                pan = res.x_best
            else:
                tilt = res.x_best
            f_best = res.f_best
        self.move(pan, tilt)
        return pan, tilt, f_best

    def acquire_sun(self, first: bool) -> bool:
        """Full sun-mode acquire. Seeds/updates the offsets and k. False on no signal."""
        self.set_state("ACQUIRE", first=first)
        c = self.cfg
        sun = self.sun()
        pan0, tilt0 = self.predicted_cmd(sun.az_deg, sun.el_deg)
        hw = c.acquire.first_half_width_deg if first else c.acquire.later_half_width_deg
        pan, tilt, _ = self._acquire_passes(pan0, tilt0, hw)
        if pan is None:
            return False
        sun = self.sun()
        az_meas = angdiff(sun.az_deg, self.heading_true_deg + c.servo.pan_sign * pan)
        el_meas = sun.el_deg - c.servo.tilt_sign * tilt
        self._check_offset("az_offset", az_meas, c.pointing.az_offset_init_deg)
        self._check_offset("el_offset", el_meas, c.pointing.el_offset_init_deg)
        if first:                                    # bootstrap: first sample of each estimator
            self.az.reset(az_meas, BOOTSTRAP_SIGMA_DEG)
            self.el.reset(el_meas, BOOTSTRAP_SIGMA_DEG)
        else:
            self.az.add(az_meas, BOOTSTRAP_SIGMA_DEG)
            self.el.add(el_meas, BOOTSTRAP_SIGMA_DEG)
        peak = self.read_panel()
        if self.k_mA <= 0.0 and c.cloud.assume_clear_start:
            self.k_mA = estimate_k_mA(peak.isc_mA, sun.el_deg)
            self.log.event("k_clear_estimated", k_clear_mA=self.k_mA, isc_mA=peak.isc_mA,
                           sun_el_deg=sun.el_deg)
        self.log.event("acquired", first=first, pan_deg=pan, tilt_deg=tilt, isc_mA=peak.isc_mA,
                       az_offset_deg=self.az.value_deg, el_offset_deg=self.el.value_deg)
        self._rejects = 0
        return True

    def _check_offset(self, name: str, value: float, init: float) -> None:
        lim = self.cfg.pointing.max_bootstrap_offset_deg
        if abs(value - init) > lim:
            raise Fault(BOOTSTRAP_FAULT_MSG % (name, value, lim))

    # ------------------------------------------------------------------ refine (6.4)
    def _scan_axis(self, axis: str, pan_c: float, tilt_c: float, spread: float,
                   sun: Optional[SunPosition]):
        """One cosine-fit scan on one axis about (pan_c, tilt_c). Logs scan.csv rows."""
        r = self.cfg.refine
        center = pan_c if axis == "pan" else tilt_c

        def measure(cmd: float) -> PanelReading:
            self.check_stop()
            self.move(cmd if axis == "pan" else pan_c, tilt_c if axis == "pan" else cmd)
            reading = self.read_panel(r.samples_per_point)
            if sun is not None and self.k_mA > 0.0 and cloud_ratio(
                    reading.isc_mA, sun.el_deg, self.k_mA, self.cos_i_pred(sun)) < self.cfg.cloud.hold_enter_ratio:
                raise _ScanAbort("cloud during %s scan" % axis)
            return reading

        pts, dur = run_scan(measure, center, spread, r.n_points, r.scan_order, self.rng,
                            self.rig.servos.limits_deg, self.clock.monotonic)
        gates = Gates(self.cfg.panel.min_signal_mA, 5, r.max_rms_frac, 1.0, r.max_drift_frac,
                      r.max_cond, r.max_sigma_deg, r.max_scan_s)
        res = evaluate_scan(pts, spread, dur, gates)
        t = self.clock.now_utc()
        for p in pts:
            self.log.row("scan.csv", {"scan_id": self._scan_id, "t_utc": t, "axis": axis, "k": p.k,
                                      "role": p.role, "cmd_deg": p.cmd_deg, "delta_deg": p.delta_deg,
                                      "isc_mA": p.isc_mA, "isc_std_mA": p.isc_std_mA, "n": p.n})
        return res, center

    def _log_fit(self, axis: str, res, spread: float, used=None, total=None, est=None) -> None:
        f = res.fit
        self.log.row("scan_fit.csv", {
            "scan_id": self._scan_id, "t_utc": self.clock.now_utc(), "axis": axis,
            "spread_deg": spread, "n_points": sum(1 for p in res.points if p.role == "point"),
            "a": f.a if f else None, "b": f.b if f else None, "c": f.c if f else None,
            "delta_star_deg": f.delta_star_deg if f else None, "amp_mA": f.amp if f else None,
            "rms_resid_mA": f.rms if f else None, "cond2_MtM": f.cond2 if f else None,
            "sigma_delta_deg": f.sigma_delta_deg if f else None, "accepted": res.accepted,
            "reject_reason": res.reject_reason, "offset_used_deg": used, "offset_total_deg": total,
            "offset_est_after_deg": est.value_deg if est else None,
            "offset_est_se_deg": est.se_deg if est else None})

    def refine(self) -> None:
        """Scan pan then tilt about the prediction; accepted scans update the offsets."""
        c = self.cfg
        self._scan_id += 1
        spread, self._spread_deg = self._spread_deg, c.refine.spread_deg
        rejected = False
        try:
            for axis in ("pan", "tilt"):
                sun = self.sun()
                pan_c, tilt_c = self._clamped(*self.predicted_cmd(sun.az_deg, sun.el_deg))
                est = self.az if axis == "pan" else self.el
                used = est.value_deg
                res, center = self._scan_axis(axis, pan_c, tilt_c, spread, sun)
                if not res.accepted:
                    rejected = True
                    self._log_fit(axis, res, spread, used, None, est)
                    self.log.event("scan_rejected", "WARNING", scan_id=self._scan_id, axis=axis,
                                   reason=res.reject_reason)
                    continue
                peak_cmd = center + res.fit.delta_star_deg
                if axis == "pan":
                    total = angdiff(sun.az_deg, self.heading_true_deg + c.servo.pan_sign * peak_cmd)
                    self._check_offset("az_offset", total, c.pointing.az_offset_init_deg)
                else:
                    total = sun.el_deg - c.servo.tilt_sign * peak_cmd
                    self._check_offset("el_offset", total, c.pointing.el_offset_init_deg)
                d = abs(res.fit.delta_star_deg)      # disagreement monitor
                if d > 1.0 and d > 3.0 * max(est.se_deg, res.fit.sigma_delta_deg):
                    self._drift_count[axis] += 1
                    if self._drift_count[axis] >= 2:
                        self.flags.add("MODEL_DRIFT")
                        self._spread_deg = min(20.0, spread * 4.0 / 3.0)
                        self.log.event("model_drift", "WARNING", axis=axis, delta_star_deg=d,
                                       hint="heading drift or bumped mount? next scan widened")
                else:
                    self._drift_count[axis] = 0
                    self.flags.discard("MODEL_DRIFT")
                est.add(total, res.fit.sigma_delta_deg)
                self._log_fit(axis, res, spread, used, total, est)
        except _ScanAbort as exc:
            self.log.event("scan_aborted", "WARNING", scan_id=self._scan_id, why=str(exc))
            self.point_at_sun(settle=True)
            return
        self.point_at_sun(settle=True)
        self._rejects = self._rejects + 1 if rejected else 0
        if self._rejects >= 2:                       # two bad scans in a row: re-acquire, never jump
            self.log.event("reacquire", "WARNING", why="two consecutive rejected scans")
            self._rejects = 0
            if self.acquire_sun(first=False):
                self.set_state("TRACK")
            else:
                self.set_state("HOLD", why="no signal on re-acquire")

    # ------------------------------------------------------------------ fixed-panel check (6.7)
    def fixed_check(self) -> None:
        t = self.cfg.track
        sun = self.sun()
        before = self.read_panel()
        e_n = 90.0 - t.fixed_panel_tilt_from_horizontal_deg
        self.move(*self.predicted_cmd(t.fixed_panel_az_deg, e_n))
        cos_fixed = self.cos_i_pred(sun)             # uses the clamped pose actually commanded
        end = self.clock.monotonic() + t.fixed_check_duration_s
        while self.clock.monotonic() < end:
            self.check_stop()
            self.clock.sleep(min(1.0, t.fixed_check_duration_s))
        meas = self.read_panel()
        self.point_at_sun(settle=True)
        after = self.read_panel()
        i_n = 0.5 * (before.isc_mA + after.isc_mA)
        self.log.row("fixed_check.csv", {
            "t_utc": self.clock.now_utc(), "isc_fixed_meas_mA": meas.isc_mA,
            "isc_in_before_mA": before.isc_mA, "isc_in_after_mA": after.isc_mA,
            "isc_fixed_pred_mA": i_n * max(0.0, cos_fixed), "cos_i_fixed": cos_fixed})
        if i_n > 0 and abs(after.isc_mA - before.isc_mA) / i_n > self.cfg.refine.max_drift_frac:
            self.log.event("fixed_check_drift", "WARNING", why="light changed during the check")

    # ------------------------------------------------------------------ cycle row
    def _cycle_row(self, sun: Optional[SunPosition], r: Optional[PanelReading], rho: Optional[float],
                   clear: Optional[float], extra_flags=()) -> None:
        pan, tilt = self.rig.servos.commanded()
        pp, tp = self.rig.servos.pulses_us()
        flags = sorted(set(self.flags) | set(extra_flags))
        self.log.row("cycle.csv", {
            "t_utc": self.clock.now_utc(), "t_mono_s": self.clock.monotonic(), "state": self.state,
            "sun_az_deg": sun.az_deg if sun else None, "sun_el_deg": sun.el_deg if sun else None,
            "heading_true_deg": self.heading_true_deg, "az_offset_deg": self.az.value_deg,
            "el_offset_deg": self.el.value_deg, "pan_cmd_deg": pan, "tilt_cmd_deg": tilt,
            "pan_pulse_us": pp, "tilt_pulse_us": tp, "isc_mA": r.isc_mA if r else None,
            "isc_std_mA": r.isc_std_mA if r else None, "bus_V": r.bus_V if r else None,
            "clear_isc_mA": clear, "cloud_ratio": rho if rho is not None and math.isfinite(rho) else None,
            "imu_cal_sys": self.imu_cal.sys if self.imu_cal else None,
            "imu_cal_mag": self.imu_cal.mag if self.imu_cal else None, "flags": "|".join(flags)})

    def _tick_sleep(self, t_tick: float) -> None:
        self.clock.sleep(max(0.0, self.cfg.track.tick_s - (self.clock.monotonic() - t_tick)))

    # ------------------------------------------------------------------ sun session (9)
    def session_sun(self) -> None:
        c = self.cfg
        self.preflight()
        waited = 0.0
        while self.sun().el_deg < c.pointing.min_elevation_deg:      # start gating
            if waited >= c.runtime.wait_for_sun_max_s:
                self.exit_reason = "sun below min elevation"
                self.park()
                return
            self.log.event("waiting_for_sun", sun_el_deg=self.sun().el_deg, waited_s=waited)
            for _ in range(30):
                self.check_stop()
                self.clock.sleep(1.0)
            waited += 30.0
        self.coarse_align()
        t_start = self.clock.monotonic()
        while not self.acquire_sun(first=True):                      # no signal: hold and retry
            self.set_state("HOLD", why="no signal")
            self.point_at_sun()
            for _ in range(60):
                self.check_stop()
                self.clock.sleep(1.0)
            if self.sun().el_deg < c.pointing.min_elevation_deg or self._over_duration(t_start):
                self.exit_reason = "no signal"
                self.park()
                return
        self.set_state("TRACK")
        self.track(t_start)
        self.park()

    def _over_duration(self, t_start: float) -> bool:
        d = self.opts.duration_s
        return d is not None and self.clock.monotonic() - t_start >= d

    def track(self, t_start: float) -> None:
        c, tr, cl = self.cfg, self.cfg.track, self.cfg.cloud
        now = self.clock.monotonic()
        last_predict = -math.inf
        last_scan_end = last_fixed_end = now
        next_scan, next_fixed = now + tr.scan_interval_s, now + tr.fixed_check_interval_s
        low = high = 0
        hold_start = 0.0
        while True:
            t_tick = self.clock.monotonic()
            self.check_stop()
            if self._over_duration(t_start):
                self.exit_reason = "duration reached"
                return
            sun = self.sun()
            if sun.el_deg < c.pointing.min_elevation_deg:
                self.exit_reason = "sun below min elevation"
                return
            if t_tick - last_predict >= tr.predict_update_s:
                self.point_at_sun(sun)
                last_predict = t_tick
                try:
                    self.imu_cal = self._retry(self.rig.imu.calibration, "imu.calibration")
                except HardwareError:
                    pass
            try:
                r = self.read_panel()
            except HardwareError:
                self._cycle_row(sun, None, None, None, ("HW_ERROR",))
                self._tick_sleep(t_tick)
                continue
            self._last_reading = r
            clear = clear_isc_mA(sun.el_deg, self.k_mA) if self.k_mA > 0 else None
            rho = cloud_ratio(r.isc_mA, sun.el_deg, self.k_mA, self.cos_i_pred(sun)) \
                if self.k_mA > 0 else math.inf
            cloudy = rho < cl.hold_enter_ratio
            if self.state == "TRACK":
                low = low + 1 if cloudy else 0
                if low >= cl.hold_enter_samples:
                    self.set_state("HOLD", cloud_ratio=rho)
                    hold_start, high = t_tick, 0
            elif self.state == "HOLD":
                high = high + 1 if rho > cl.hold_exit_ratio else 0
                if high >= cl.hold_exit_samples:
                    low = 0
                    held = t_tick - hold_start
                    if held > cl.reacquire_after_hold_s and not self.acquire_sun(first=False):
                        self.set_state("HOLD", why="no signal on re-acquire")
                        hold_start, high = self.clock.monotonic(), 0
                    else:
                        self.set_state("TRACK", held_s=held)
                        last_predict = -math.inf
                        next_scan = max(next_scan, self.clock.monotonic() + tr.scan_guard_s)
            extra = (["CLOUD"] if cloudy else []) + (["OVERRANGE"] if r.overrange else [])
            self._cycle_row(sun, r, rho, clear, extra)
            if self.on_tick is not None:
                self.on_tick(self)
            if self.state == "TRACK" and not cloudy:
                if t_tick >= next_scan and t_tick - last_fixed_end >= tr.scan_guard_s:
                    self.refine()
                    last_scan_end = self.clock.monotonic()
                    next_scan = t_tick + tr.scan_interval_s
                    last_predict = last_scan_end
                elif t_tick >= next_fixed and t_tick - last_scan_end >= tr.scan_guard_s \
                        and next_scan - t_tick >= tr.scan_guard_s:
                    self.fixed_check()
                    last_fixed_end = self.clock.monotonic()
                    next_fixed = t_tick + tr.fixed_check_interval_s
                    last_predict = last_fixed_end
            self._tick_sleep(t_tick)

    # ------------------------------------------------------------------ lamp session (6.3)
    def _lamp_acquire(self, half_width: float) -> Optional[float]:
        """Acquire on the lamp about the current pointing, then polish each axis with a
        cosine-fit scan (demonstrates the refine fit indoors). Returns the peak Isc or None."""
        self.set_state("ACQUIRE", mode="lamp")
        pan, tilt, _ = self._acquire_passes(*self.rig.servos.commanded(), half_width)
        if pan is None:
            return None
        self._scan_id += 1
        for axis in ("pan", "tilt"):
            res, center = self._scan_axis(axis, pan, tilt, self.cfg.refine.spread_deg, None)
            self._log_fit(axis, res, self.cfg.refine.spread_deg)
            if res.accepted:
                if axis == "pan":
                    pan = center + res.fit.delta_star_deg
                else:
                    tilt = center + res.fit.delta_star_deg
            self.move(pan, tilt)
        peak = self.read_panel().isc_mA
        self.log.event("lamp_acquired", pan_deg=pan, tilt_deg=tilt, isc_mA=peak)
        return peak

    def session_lamp(self) -> None:
        a = self.cfg.acquire
        self.preflight()
        t_start = self.clock.monotonic()
        peak = self._lamp_acquire(a.lamp_half_width_deg)
        while True:
            t_tick = self.clock.monotonic()
            self.check_stop()
            if self._over_duration(t_start):
                self.exit_reason = "duration reached"
                break
            if peak is None:                                         # nothing seen: retry in 5 s
                self.set_state("HOLD", why="no signal")
                for _ in range(5):
                    self.check_stop()
                    self.clock.sleep(1.0)
                peak = self._lamp_acquire(a.lamp_half_width_deg)
                continue
            self.set_state("TRACK")
            try:
                r = self.read_panel()
            except HardwareError:
                self._tick_sleep(t_tick)
                continue
            self._cycle_row(None, r, None, None)
            if self.on_tick is not None:
                self.on_tick(self)
            if r.isc_mA < (1.0 - a.lamp_reacquire_drop_frac) * peak:
                self.log.event("lamp_reacquire", isc_mA=r.isc_mA, peak_mA=peak)
                peak = self._lamp_acquire(a.lamp_reacquire_half_width_deg)
                continue
            peak = max(peak, r.isc_mA)
            self._tick_sleep(t_tick)
        self.park()

    # ------------------------------------------------------------------ single-command bodies
    def only_preflight(self) -> None:
        self.preflight()
        self.park()

    def only_turn(self) -> None:
        self.preflight()
        self.coarse_align()
        self.park()

    def only_acquire(self) -> None:
        self.preflight()
        if self.opts.mode == "lamp":
            self._lamp_acquire(self.cfg.acquire.lamp_half_width_deg)
        else:
            self.opts.skip_turn = True               # acquire alone never drives the wheels
            self.coarse_align()
            self.acquire_sun(first=True)
        self.park()

    def static_log(self, minutes: float, pan_deg: float, tilt_deg: float, hz: float = 10.0) -> None:
        """Hold a fixed pose and log single-sample Isc at ~10 Hz (noise model)."""
        self.set_state("STATIC")
        self.move(pan_deg, tilt_deg)
        end = self.clock.monotonic() + 60.0 * minutes
        while self.clock.monotonic() < end:
            t_tick = self.clock.monotonic()
            self.check_stop()
            r = self.read_panel(1)
            self.log.row("static.csv", {"t_utc": self.clock.now_utc(), "isc_mA": r.isc_mA,
                                        "bus_V": r.bus_V})
            self.clock.sleep(max(0.0, 1.0 / hz - (self.clock.monotonic() - t_tick)))
        self.park()
