import csv
import json
from datetime import datetime, timezone

import pytest

from solar_tracker.clock import SimClock
from solar_tracker.logging_ import HEADERS, SessionLogger

SPEC_CYCLE = ("t_utc, t_mono_s, state, sun_az_deg, sun_el_deg, heading_true_deg, az_offset_deg, "
              "el_offset_deg, pan_cmd_deg, tilt_cmd_deg, pan_pulse_us, tilt_pulse_us, isc_mA, "
              "isc_std_mA, bus_V, clear_isc_mA, cloud_ratio, imu_cal_sys, imu_cal_mag, flags")


def make(tmp_path):
    clock = SimClock(datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc))
    return SessionLogger(str(tmp_path), "unit", clock, fsync=True), clock


def test_headers_match_spec():
    assert HEADERS["cycle.csv"] == SPEC_CYCLE.split(", ")
    assert HEADERS["scan.csv"] == "scan_id t_utc axis k role cmd_deg delta_deg isc_mA isc_std_mA n".split()
    assert HEADERS["turn.csv"][0] == "t_s" and HEADERS["turn.csv"][-2:] == ["left_cmd", "right_cmd"]
    assert HEADERS["static.csv"] == ["t_utc", "isc_mA", "bus_V"]
    assert HEADERS["servo_cal.csv"] == ["servo", "direction", "pulse_us", "measured_deg"]
    assert set(HEADERS) == {"cycle.csv", "scan.csv", "scan_fit.csv", "acquire.csv", "turn.csv",
                            "fixed_check.csv", "static.csv", "servo_cal.csv"}


def test_rows_are_on_disk_immediately(tmp_path):
    log, clock = make(tmp_path)
    assert log.dir.name == "20261116_150000Z_unit"
    for i in range(3):
        log.row("static.csv", {"t_utc": clock.now_utc(), "isc_mA": 100.0 + i, "bus_V": 0.01})
        with open(log.dir / "static.csv", newline="") as fh:        # file still open for writing
            got = list(csv.reader(fh))
        assert got[0] == HEADERS["static.csv"] and len(got) == i + 2
    log.event("hello", "WARNING", x=1)
    assert json.loads((log.dir / "events.jsonl").read_text())["event"] == "hello"
    with pytest.raises(KeyError):
        log.row("static.csv", {"not_a_column": 1})
    log.write_session({"a": 1})
    log.close()
    assert json.loads((log.dir / "session.json").read_text()) == {"a": 1}
    log2, _ = make(tmp_path)                                         # same second: new folder
    assert log2.dir.name == "20261116_150000Z_unit_2"
    log2.close()
