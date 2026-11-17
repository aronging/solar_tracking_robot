"""Session logging: one folder per run with CSV files, events.jsonl, session.json, run.log.

Every CSV row is written and flushed immediately; with fsync=True (real hardware) it
is also os.fsync'd, because the Pi may lose power. Formats: spec section 11.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

HEADERS: Dict[str, list] = {
    "cycle.csv": "t_utc t_mono_s state sun_az_deg sun_el_deg heading_true_deg az_offset_deg "
                 "el_offset_deg pan_cmd_deg tilt_cmd_deg pan_pulse_us tilt_pulse_us isc_mA "
                 "isc_std_mA bus_V clear_isc_mA cloud_ratio imu_cal_sys imu_cal_mag flags".split(),
    "scan.csv": "scan_id t_utc axis k role cmd_deg delta_deg isc_mA isc_std_mA n".split(),
    "scan_fit.csv": "scan_id t_utc axis spread_deg n_points a b c delta_star_deg amp_mA "
                    "rms_resid_mA cond2_MtM sigma_delta_deg accepted reject_reason offset_used_deg "
                    "offset_total_deg offset_est_after_deg offset_est_se_deg".split(),
    "acquire.csv": "acq_id t_utc axis phase iter x_deg f_mA interval_width_deg x_golden_deg "
                   "x_parabolic_deg x_best_deg".split(),
    "turn.csv": "t_s heading_true_deg target_deg err_deg u p_term i_term d_term integral_mode "
                "left_cmd right_cmd".split(),
    "fixed_check.csv": "t_utc isc_fixed_meas_mA isc_in_before_mA isc_in_after_mA "
                       "isc_fixed_pred_mA cos_i_fixed".split(),
    "static.csv": "t_utc isc_mA bus_V".split(),
    "servo_cal.csv": "servo direction pulse_us measured_deg".split(),
}


def _fmt(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return "%.6g" % v if abs(v) < 1e15 else repr(v)
    if isinstance(v, datetime):
        return v.isoformat(timespec="milliseconds")
    return v


class SessionLogger:
    """Creates ``<root>/YYYYMMDD_HHMMSSZ_<command>/`` and writes the session files."""

    def __init__(self, root: str, command: str, clock, fsync: bool = True, verbose: bool = False):
        self.clock = clock
        self.fsync = fsync
        stamp = clock.now_utc().strftime("%Y%m%d_%H%M%SZ")
        base = Path(root) / ("%s_%s" % (stamp, command))
        self.dir = base
        n = 1
        while self.dir.exists():
            n += 1
            self.dir = Path("%s_%d" % (base, n))
        self.dir.mkdir(parents=True)
        self._files: Dict[str, Any] = {}
        self._writers: Dict[str, Any] = {}
        self._events = open(self.dir / "events.jsonl", "w", encoding="utf-8")
        self.log = logging.getLogger("solar_tracker")
        self.log.setLevel(logging.DEBUG)
        self.log.propagate = False
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        self._handlers = [logging.StreamHandler(),
                          logging.FileHandler(self.dir / "run.log", encoding="utf-8")]
        self._handlers[0].setLevel(logging.DEBUG if verbose else logging.INFO)
        for h in self._handlers:
            h.setFormatter(fmt)
            self.log.addHandler(h)

    def _sync(self, fh) -> None:
        fh.flush()
        if self.fsync:
            os.fsync(fh.fileno())

    def row(self, name: str, values: Mapping[str, Any]) -> None:
        """Append one row to a CSV file (header written on first use)."""
        if name not in self._writers:
            fh = open(self.dir / name, "w", newline="", encoding="utf-8")
            self._files[name] = fh
            self._writers[name] = csv.writer(fh)
            self._writers[name].writerow(HEADERS[name])
        unknown = set(values) - set(HEADERS[name])
        if unknown:
            raise KeyError("%s: unknown columns %s" % (name, sorted(unknown)))
        self._writers[name].writerow([_fmt(values.get(col)) for col in HEADERS[name]])
        self._sync(self._files[name])

    def event(self, event: str, level: str = "INFO", **fields: Any) -> None:
        """Append one JSON line to events.jsonl and echo it to the run log."""
        rec = {"t_utc": self.clock.now_utc().isoformat(timespec="milliseconds"),
               "level": level, "event": event}
        rec.update(fields)
        self._events.write(json.dumps(rec, default=str) + "\n")
        self._sync(self._events)
        detail = " ".join("%s=%s" % (k, _fmt(v)) for k, v in fields.items() if k != "traceback")
        self.log.log(getattr(logging, level, logging.INFO), "%s %s", event, detail)

    def write_session(self, data: Mapping[str, Any]) -> None:
        with open(self.dir / "session.json", "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
            self._sync(fh)

    def close(self) -> None:
        for fh in list(self._files.values()) + [self._events]:
            if not fh.closed:
                fh.close()
        for h in self._handlers:
            self.log.removeHandler(h)
            h.close()
        self._handlers = []


def git_commit(cwd: Optional[str] = None) -> Optional[str]:
    """Short git commit hash of the code folder, or None."""
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd, capture_output=True,
                             text=True, timeout=3)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None
