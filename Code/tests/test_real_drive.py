"""RealDrive with fake lab PWM_Motor objects: duty mapping, clamp, lazy creation, stop."""
import pytest

from solar_tracker.config import ConfigError, load_config
from solar_tracker.hardware.real import RealDrive


class FakeMotor:
    def __init__(self, fwd, rv):
        self.channels, self.duties, self.stops = (fwd, rv), [], 0

    def set_motor_duty(self, duty):
        self.duties.append(duty)

    def stop_motor(self):
        self.stops += 1


def make(*overrides):
    made = []

    def factory(fwd, rv):
        made.append(FakeMotor(fwd, rv))
        return made[-1]

    cfg = load_config(overrides=overrides, use_robot_file=False)
    return RealDrive(cfg, factory), made


def test_refuses_until_configured_and_never_touches_a_wheel():
    drive, made = make()
    with pytest.raises(ConfigError, match="drive.left_motor_channels"):
        drive.set_turn(0.3)
    drive.stop()                                # never raises, never creates a motor
    assert made == []


def test_duty_mapping_clamp_and_stop():
    drive, made = make("drive.left_motor_channels=[0, 1]", "drive.right_motor_channels=[2, 3]",
                       "drive.max_duty=0.5", "drive.right_sign=-1")
    drive.stop()
    assert made == []                           # lazy: nothing until the first set_turn
    drive.set_turn(0.3)
    drive.set_turn(-2.0)                        # clamped to -max_duty
    left, right = made
    assert len(made) == 2 and left.channels == (0, 1) and right.channels == (2, 3)
    assert left.duties == pytest.approx([30.0, -50.0])
    assert right.duties == pytest.approx([30.0, -50.0])      # -u * right_sign(-1)
    drive.stop()
    drive.stop()                                # idempotent
    assert left.stops == right.stops == 2


def test_turn_sign_and_stop_never_raises():
    drive, made = make("drive.left_motor_channels=[0, 1]", "drive.right_motor_channels=[2, 3]",
                       "drive.turn_sign=-1")
    drive.set_turn(0.2)
    assert made[0].duties == pytest.approx([-20.0]) and made[1].duties == pytest.approx([20.0])

    def boom():
        raise OSError("bus")
    made[0].stop_motor = boom
    drive.stop()                                # left fails twice, right still stopped
    assert made[1].stops == 1
