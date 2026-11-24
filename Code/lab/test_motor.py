from motor_servo_pwm import Servo, PWM_Motor
import time

# change the channel number inside parentheses to what you connected to
motor1 = PWM_Motor(0, 1)
motor2 = PWM_Motor(2, 3)
servo1 = Servo(13)
servo2 = Servo(12)

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