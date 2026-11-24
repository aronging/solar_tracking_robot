"""Configuration: nested dataclasses loaded from TOML (spec section 10).

Load order: config/default.toml -> config/robot.toml (if present) -> extra files (--config)
-> ``section.key=value`` overrides (--set). Units are in the key names. Hardware values that are unknown are
None; TOML has no null, so a required key is simply absent (commented out) in the file.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:                                    # Python >= 3.11
    import tomllib as _toml
except ImportError:                     # pragma: no cover - Python 3.9/3.10 on the Pi
    import tomli as _toml               # type: ignore

CODE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TOML = CODE_DIR / "config" / "default.toml"
ROBOT_TOML = CODE_DIR / "config" / "robot.toml"      # the one file the team edits


class ConfigError(ValueError):
    """Bad or missing configuration. The message names the exact key."""


@dataclass
class Site:
    name: str = "College Station"
    lat_deg: float = 30.6280
    lon_deg: float = -96.3344           # east positive
    declination_deg: float = 2.0        # magnetic declination, east positive


@dataclass
class Hardware:
    backend: str = "real"               # "real" | "sim"
    ina219_address: int = 0x41
    imu_address: int = 0x28
    mux_channel_panel: Optional[int] = None    # REQUIRED for real hardware
    mux_channel_imu: Optional[int] = None      # REQUIRED for real hardware
    servo_channel_pan: Optional[int] = None    # REQUIRED for real hardware
    servo_channel_tilt: Optional[int] = None   # REQUIRED for real hardware
    overrange_mA: float = 380.0


@dataclass
class Servo:
    pan_sign: int = 1
    tilt_sign: int = 1
    limit_deg: float = 85.0
    slew_deg_per_s: float = 60.0
    settle_s: float = 0.6
    pulse_min_us: float = 500.0
    pulse_max_us: float = 2500.0
    center_us: float = 1500.0
    deg_per_us: float = 0.09
    calibration_file: str = "config/servo_cal.json"


@dataclass
class Drive:
    left_motor_channels: Optional[list] = None    # [fwd, rv] PCA channels; REQUIRED for the real turn
    right_motor_channels: Optional[list] = None   # [fwd, rv] PCA channels; REQUIRED for the real turn
    turn_sign: int = 1
    left_sign: int = 1
    right_sign: int = 1
    max_duty: float = 0.5
    min_turn_duty: float = 0.25


@dataclass
class Panel:
    n_samples_default: int = 8
    zero_offset_mA: float = 0.0
    min_signal_mA: float = 5.0
    k_clear_mA: float = 0.0                    # 0 = estimate from the first clear-sky acquire


@dataclass
class Pointing:
    az_offset_init_deg: float = 0.0
    el_offset_init_deg: float = 0.0
    min_elevation_deg: float = 10.0
    park_pan_deg: float = 0.0
    park_tilt_deg: float = 0.0
    max_bootstrap_offset_deg: float = 40.0


@dataclass
class Align:
    target_heading_true_deg: float = 180.0
    tol_deg: float = 2.0
    hold_s: float = 1.0
    max_turn_s: float = 40.0
    loop_hz: float = 20.0
    kp: float = 0.02
    ki: float = 0.002
    kd: float = 0.004
    d_filter_tau_s: float = 0.15
    integral_mode: str = "trapezoid"
    imu_mag_cal_min: int = 3


@dataclass
class Acquire:
    n_coarse: int = 9
    first_half_width_deg: float = 40.0
    later_half_width_deg: float = 15.0
    tol_deg: float = 1.5
    max_evals: int = 24
    n_passes: int = 2
    samples_per_point: int = 8
    lamp_half_width_deg: float = 60.0
    lamp_reacquire_half_width_deg: float = 30.0
    lamp_reacquire_drop_frac: float = 0.05


@dataclass
class Track:
    tick_s: float = 1.0
    predict_update_s: float = 60.0
    scan_interval_s: float = 720.0
    scan_guard_s: float = 120.0
    limit_replan_s: float = 300.0
    fixed_check_interval_s: float = 900.0
    fixed_check_duration_s: float = 10.0
    fixed_panel_az_deg: float = 180.0
    fixed_panel_tilt_from_horizontal_deg: float = 45.0


@dataclass
class Refine:
    spread_deg: float = 15.0
    n_points: int = 7
    scan_order: str = "shuffled"
    samples_per_point: int = 8
    max_scan_s: float = 30.0
    max_rms_frac: float = 0.03
    max_drift_frac: float = 0.03
    max_cond: float = 2.0e5
    max_sigma_deg: float = 3.0
    offset_forget: float = 1.0


@dataclass
class Cloud:
    hold_enter_ratio: float = 0.70
    hold_exit_ratio: float = 0.80
    hold_enter_samples: int = 5
    hold_exit_samples: int = 10
    reacquire_after_hold_s: float = 300.0
    assume_clear_start: bool = True


@dataclass
class Runtime:
    watchdog_s: float = 10.0
    wait_for_sun_max_s: float = 1800.0
    log_dir: str = "logs"


@dataclass
class Config:
    site: Site = field(default_factory=Site)
    hardware: Hardware = field(default_factory=Hardware)
    servo: Servo = field(default_factory=Servo)
    drive: Drive = field(default_factory=Drive)
    panel: Panel = field(default_factory=Panel)
    pointing: Pointing = field(default_factory=Pointing)
    align: Align = field(default_factory=Align)
    acquire: Acquire = field(default_factory=Acquire)
    track: Track = field(default_factory=Track)
    refine: Refine = field(default_factory=Refine)
    cloud: Cloud = field(default_factory=Cloud)
    runtime: Runtime = field(default_factory=Runtime)

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _set(cfg: Config, section: str, key: str, value: Any) -> None:
    sec = getattr(cfg, section, None)
    if sec is None or not dataclasses.is_dataclass(sec):
        raise ConfigError("unknown config section [%s]" % section)
    if key not in {f.name for f in dataclasses.fields(sec)}:
        raise ConfigError("unknown config key %s.%s" % (section, key))
    current = getattr(sec, key)
    if isinstance(current, float) and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    setattr(sec, key, value)


def _apply(cfg: Config, data: Dict[str, Any]) -> None:
    for section, values in data.items():
        if not isinstance(values, dict):
            raise ConfigError("top-level key %r must be a [section]" % section)
        for key, value in values.items():
            _set(cfg, section, key, value)


def _parse_value(text: str) -> Any:
    if text.strip().lower() in ("none", "null"):
        return None
    try:
        return _toml.loads("v = " + text)["v"]
    except Exception:
        return text                       # bare string


def validate(cfg: Config) -> None:
    def check(ok: bool, key: str, why: str) -> None:
        if not ok:
            raise ConfigError("%s %s" % (key, why))

    check(-90 <= cfg.site.lat_deg <= 90, "site.lat_deg", "must be in [-90, 90]")
    check(-180 <= cfg.site.lon_deg <= 180, "site.lon_deg", "must be in [-180, 180]")
    check(cfg.hardware.backend in ("real", "sim"), "hardware.backend", "must be 'real' or 'sim'")
    check(cfg.servo.pan_sign in (1, -1), "servo.pan_sign", "must be +1 or -1")
    check(cfg.servo.tilt_sign in (1, -1), "servo.tilt_sign", "must be +1 or -1")
    check(0 < cfg.servo.limit_deg <= 90, "servo.limit_deg", "must be in (0, 90]")
    check(cfg.servo.pulse_min_us < cfg.servo.center_us < cfg.servo.pulse_max_us,
          "servo.pulse_min_us/center_us/pulse_max_us", "must be increasing")
    check(cfg.servo.slew_deg_per_s > 0, "servo.slew_deg_per_s", "must be positive")
    check(0 < cfg.drive.max_duty <= 1, "drive.max_duty", "must be in (0, 1]")
    check(cfg.drive.turn_sign in (1, -1), "drive.turn_sign", "must be +1 or -1")
    for side in ("left", "right"):
        ch = getattr(cfg.drive, side + "_motor_channels")
        check(ch is None or (isinstance(ch, list) and len(ch) == 2 and len(set(ch)) == 2 and
                             all(type(c) is int and 0 <= c <= 15 for c in ch)),
              "drive.%s_motor_channels" % side, "must be [fwd, rv]: two different ints 0..15")
    check(cfg.align.integral_mode in ("euler", "trapezoid", "simpson"), "align.integral_mode",
          "must be euler|trapezoid|simpson")
    check(10 <= cfg.refine.spread_deg <= 20, "refine.spread_deg", "must be in [10, 20]")
    check(5 <= cfg.refine.n_points <= 7, "refine.n_points", "must be in [5, 7]")
    check(cfg.refine.scan_order in ("sweep", "shuffled"), "refine.scan_order",
          "must be sweep|shuffled")
    check(0 < cfg.refine.offset_forget <= 1, "refine.offset_forget", "must be in (0, 1]")
    check(cfg.acquire.n_coarse >= 3, "acquire.n_coarse", "must be >= 3")
    check(cfg.cloud.hold_enter_ratio < cfg.cloud.hold_exit_ratio, "cloud.hold_enter_ratio",
          "must be below cloud.hold_exit_ratio")
    check(cfg.track.tick_s > 0, "track.tick_s", "must be positive")


def load_config(paths: Iterable[str] = (), overrides: Iterable[str] = (),
                use_default_file: bool = True, use_robot_file: bool = True) -> Config:
    """Build the resolved Config. ``overrides`` are 'section.key=value' strings.
    config/robot.toml is loaded after default.toml when it exists (tests pass
    use_robot_file=False to get the pristine defaults)."""
    cfg = Config()
    files = [f for f, on in ((DEFAULT_TOML, use_default_file),
                             (ROBOT_TOML, use_default_file and use_robot_file))
             if on and f.exists()] + [Path(p) for p in paths]
    for path in files:
        try:
            with open(path, "rb") as fh:
                _apply(cfg, _toml.load(fh))
        except OSError as exc:
            raise ConfigError("cannot read config file %s: %s" % (path, exc))
        except _toml.TOMLDecodeError as exc:
            raise ConfigError("%s: %s" % (path, exc))
    for item in overrides:
        if "=" not in item or "." not in item.split("=", 1)[0]:
            raise ConfigError("--set expects section.key=value, got %r" % item)
        dotted, text = item.split("=", 1)
        section, key = dotted.strip().split(".", 1)
        _set(cfg, section, key, _parse_value(text))
    validate(cfg)
    return cfg


def require(cfg: Config, *dotted_keys: str) -> None:
    """Raise ConfigError naming the first required key that is still None. Never guess."""
    for dotted in dotted_keys:
        section, key = dotted.split(".")
        if getattr(getattr(cfg, section), key) is None:
            raise ConfigError("%s is required for real hardware but is not set "
                              "(read it from the wiring; never guess a channel)" % dotted)


REQUIRED_REAL = ("hardware.mux_channel_panel", "hardware.mux_channel_imu",
                 "hardware.servo_channel_pan", "hardware.servo_channel_tilt")
REQUIRED_DRIVE = ("drive.left_motor_channels", "drive.right_motor_channels")
