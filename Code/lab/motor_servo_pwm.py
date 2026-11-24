from board import SCL, SDA
from typing import Optional, Type
import busio 
from adafruit_pca9685 import PCA9685

class _PCA9685():
    """
        -Base Class for I2C Based PCA9685 16 Channel PWM
        -Object can be shared for Independent PWM Motor Control and Servo Control. 
        -This Base Class is Not Required but to allow simultanous PWM Motor Control and Servo the I2C Object must be shared. 
    """
    def __init__(self):
        i2c_bus = busio.I2C(SCL, SDA)               #Interface with I2C Bus (SCL, SDA)
        self.pca = PCA9685(i2c_bus, address= 0x40)  #Interface with Adafruit 16 Channel PWM Hat (Chip is Called PCA9685)
        self.pca.frequency = 100                    #(Hz) Reference Pulse Frequency **NOTE**: Greater than 200Hz causes Buzzing of Motors and Servos
               
class PWM_Motor(_PCA9685):
    def __init__(self, motor_channel_FWD, motor_channel_RV):
        """
            Inputs: Input Motor FWD Pin on PCA9685 (int)
                  Input Motor RV Pin on PCA9685 (int)
        """
        #Inherit I2C Object and PCA Object from _PCA9685 Class
        super(PWM_Motor, self).__init__()
        self.motor_channel_FWD = motor_channel_FWD  #Motor Channel FWD
        self.motor_channel_RV = motor_channel_RV    #Motor Channel RV

    def converttoHex(self, duty_cycle):
        decimal = duty_cycle/100                  #Convert Duty (0 to 100) to decimal
        maxDuty = int(0xFFFF)                     #Convert HEX to Int
        conversionInt = round(decimal * maxDuty)  #HEX Values must be Integers
        conversionHex = int(hex(conversionInt),16)
        return conversionHex
    
    def set_motor_duty(self,duty):
        """
            Sets Respective Pins to Duty Cycle Value
            Input: Motor PWM Value from -100 to 100
        """
        if duty >= 0 and duty <=100:
            #FWD and RV cannot Be activated at Same Time (I.e. Atleast on must be 0)
            self.pca.channels[self.motor_channel_RV].duty_cycle = self.converttoHex(0) #Set Reverse to 0
            self.pca.channels[self.motor_channel_FWD].duty_cycle = self.converttoHex(duty)
        elif duty < 0 and duty >=-100:
            #FWD and RV cannot Be activated at Same Time (I.e. Atleast on must be 0)
            self.pca.channels[self.motor_channel_FWD].duty_cycle = self.converttoHex(0) #Set Forward to 0 
            #PCA9685 Cannot Interpret Negative Values.
            self.pca.channels[self.motor_channel_RV].duty_cycle = self.converttoHex(-1*duty)
        else:
            print("***ERROR***:")
            print("*Out of Range Value*")

    def stop_motor(self):
        """
            Stops Motors within instance of PWM_Motor() Class
        """
        self.pca.channels[self.motor_channel_FWD].duty_cycle = self.converttoHex(0)
        self.pca.channels[self.motor_channel_RV].duty_cycle = self.converttoHex(0)


class _BaseServo(_PCA9685):  # pylint: disable-msg=too-few-public-methods
    """Shared base class that handles pulse output based on a value between 0 and 1.0
    :param ~pwmio.PWMOut pwm_out: PWM output object.
    :param int min_pulse: The minimum pulse length of the servo in microseconds.
    :param int max_pulse: The maximum pulse length of the servo in microseconds."""

    def __init__(self, servo_channel, min_pulse: int = 750, max_pulse: int = 2250) -> None:
        #Inherit I2C Object and PCA Object from _PCA9685 Class
        super(_BaseServo, self).__init__()
        self._pwm_out = self.pca.channels[servo_channel]
        self.set_pulse_width_range(min_pulse, max_pulse)

    def set_pulse_width_range(self, min_pulse: int = 750, max_pulse: int = 2250) -> None:
        """Change min and max pulse widths."""
        self._min_duty = int((min_pulse * self._pwm_out.frequency) / 1000000 * 0xFFFF)
        max_duty = (max_pulse * self._pwm_out.frequency) / 1000000 * 0xFFFF
        self._duty_range = int(max_duty - self._min_duty)

    @property
    def fraction(self) -> Optional[float]:
        """Pulse width expressed as fraction between 0.0 (`min_pulse`) and 1.0 (`max_pulse`).
        For conventional servos, corresponds to the servo position as a fraction
        of the actuation range. Is None when servo is diabled (pulsewidth of 0ms).
        """
        if self._pwm_out.duty_cycle == 0:  # Special case for disabled servos
            return None
        return (self._pwm_out.duty_cycle - self._min_duty) / self._duty_range

    @fraction.setter
    def fraction(self, value: Optional[float]) -> None:
        if value is None:
            self._pwm_out.duty_cycle = 0  # disable the motor
            return
        if not 0.0 <= value <= 1.0:
            raise ValueError("Must be 0.0 to 1.0")
        duty_cycle = self._min_duty + int(value * self._duty_range)
        self._pwm_out.duty_cycle = duty_cycle


class Servo(_BaseServo):
    def __init__(self, servo_channel2, actuation_range: int = 180, min_pulse: int = 750, max_pulse: int = 2250) -> None:
        super().__init__(servo_channel = servo_channel2, min_pulse=min_pulse, max_pulse=max_pulse)
        self.actuation_range = actuation_range
        """The physical range of motion of the servo in degrees.
        :type: float
        """
    @property
    def angle(self) -> Optional[float]:
        """The servo angle in degrees. Must be in the range ``0`` to ``actuation_range``.
        Is None when servo is disabled."""
        if self.fraction is None:  # special case for disabled servos
            return None
        return self.actuation_range * self.fraction

    @angle.setter
    def angle(self, new_angle: Optional[int]) -> None:
        if new_angle is None:  # disable the servo by sending 0 signal
            self.fraction = None
            return
        if new_angle < 0 or new_angle > self.actuation_range:
            raise ValueError("Angle out of range")
        self.fraction = new_angle / self.actuation_range


# ---------------------------------------------------------------------------------------------------------------------------
# All Code Below 'if __name__== "__main__" will NOT execute when the classes above are imported to another file (ex: from xxxx import xxxxx). 
# The code below will thereby only run when the file is run directly (ex: python3 xxxxx.py)
# The code below is used to individually test the just one motor and one servo.
# ---------------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    import time
    #Set Motor FWD and RV to PWM Hat Pins 0 and 1 Respectively
    motor1 = PWM_Motor(1, 0)
    motor2 = PWM_Motor(3, 2)
    servo1 = Servo(14)
    servo2 = Servo(15)

    try:
        while True:
            #Loop Continously
            servo1.angle = 0
            servo2.angle = 0
            motor1.set_motor_duty(10)
            motor2.set_motor_duty(10)
            time.sleep(2)
            servo1.angle = 180
            servo2.angle = 180
            motor1.set_motor_duty(-10)
            motor2.set_motor_duty(-10)
            time.sleep(2)
    #Kill Motor When (CTRL+C) Pressed (aka KeyboardInterrupt)
    finally:
        motor1.stop_motor()
        motor2.stop_motor()
        