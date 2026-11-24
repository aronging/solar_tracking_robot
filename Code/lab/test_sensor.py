from sensor_module import CreateMuxI2C, Sensor_Thread
import time

from adafruit_apds9960.apds9960 import APDS9960
from adafruit_vl53l4cd import VL53L4CD
from adafruit_bno055 import BNO055_I2C

# change the channel number to what you connected to
apds_channel = 5
vl53_channel = 4
bno_channel = 6

apds = APDS9960(CreateMuxI2C(apds_channel)) # Proximity, Light, RGB, and Gesture Sensor
apds.enable_color = True

vl53 = VL53L4CD(CreateMuxI2C(vl53_channel), 0x29) # Time of Flight Distance Sensor
vl53.inter_measurement = 0
vl53.timing_budget = 200 # refresh rate
vl53.start_ranging()

bno = BNO055_I2C(CreateMuxI2C(bno_channel)) # IMU

# create a sensor thread to collect data simultaneously
sensor = Sensor_Thread(vl53, apds, bno)
sensor.create_sensor_thread()

while True:
    print(f"TOF sensor distance: {sensor.Distance} cm")
    print(f"Color sensor: {sensor.Color}")
    print(f"Accelerometer (m/s^2): {sensor.Acceleration}")
    print(f"Gyroscope (rad/sec): {sensor.AngularVelocity}")
    time.sleep(0.5)