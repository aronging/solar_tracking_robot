import pytest

from solar_tracker.config import Config, ConfigError, load_config
from solar_tracker.hardware.real import make_real_rig
from solar_tracker.hardware.sim import make_sim_rig


def test_default_toml_matches_dataclass_defaults():
    assert load_config(use_robot_file=False).as_dict() == Config().as_dict()


def test_robot_toml_loads_and_validates():
    load_config()                               # whatever its contents, it must be valid


@pytest.mark.parametrize("key", ["mux_channel_panel", "mux_channel_imu", "servo_channel_pan",
                                 "servo_channel_tilt"])
def test_real_backend_refuses_missing_channel(key):
    keys = ["mux_channel_panel", "mux_channel_imu", "servo_channel_pan", "servo_channel_tilt"]
    cfg = load_config(overrides=["hardware.%s=1" % k for k in keys if k != key],
                      use_robot_file=False)
    with pytest.raises(ConfigError, match="hardware." + key):
        make_real_rig(cfg)                      # raises before importing any Pi library


def test_sim_backend_needs_no_channels():
    rig = make_sim_rig(load_config(overrides=['hardware.backend="sim"']))
    assert rig.panel.read(2).n == 2


def test_overrides_and_validation(tmp_path):
    site = tmp_path / "site.toml"
    site.write_text('[site]\nlat_deg = 40\n[hardware]\nservo_channel_pan = 0x0e\n')
    cfg = load_config([str(site)], ["site.lat_deg=41.5", "refine.scan_order=sweep"])
    assert cfg.site.lat_deg == 41.5 and cfg.hardware.servo_channel_pan == 14
    assert cfg.refine.scan_order == "sweep"
    for bad in ("nosuch.key=1", "site.nosuch=1", "refine.spread_deg=5", "servo.pan_sign=2",
                "align.integral_mode=rk4", "garbage", "drive.left_motor_channels=[1, 1]",
                "drive.right_motor_channels=[0, 16]", "drive.left_motor_channels=3"):
        with pytest.raises(ConfigError):
            load_config(overrides=[bad])
