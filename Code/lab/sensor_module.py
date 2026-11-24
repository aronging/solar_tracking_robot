import board
import time
from threading import Thread
from adafruit_tca9548a import TCA9548A

def CreateMuxI2C(channel):
    i2c = board.I2C()
    tca = TCA9548A(i2c)
    return tca[channel]

class Sensor_Thread():
    def __init__(self, TOF_Sensor_Obj, Color_Sensor_Obj, IMU_Obj):
        #Inherit Sensor Objects
        self.TOF_Sensor = TOF_Sensor_Obj
        self.Color_Sensor = Color_Sensor_Obj
        self.IMU = IMU_Obj

        #Create Logging Data Variables
        #If you need more data from sensors, add variables below and assign sensor reading to them in _read_data
        self.Distance = 0                       # Distance Reading in [cm]
        self.Color = [None, None, None, None]   # [r, g, b, c]
        self.Acceleration = [0, 0, 0]           # Acceleration along 3 directions x, y, z in m/s^2
        self.AngularVelocity = [0, 0, 0]        # Angular velocity along 3 directions x, y, z in rad/s

    def create_sensor_thread(self):
        #Create Thread to Collect All Sensor Readings Independent from Other Processes
        #Executing _read_data() function as thread to parse and log data
        self.thread = Thread(target = self._read_data)
        self.start_sensor_thread()
    def start_sensor_thread(self):
        self.thread.start() #Start Threaded Object
    def kill_sensor_thread(self):
        self.thread.join()  #OPTIONAL: Use If Threaded Process Must be Killed or Restarted
    def _read_data(self):
        #While Loop to Collect All Sensor Data. This will Run as a Thread
        while True:
            #Only Need to Wait for One Data Register to Pass Data 
            #For Simplicity Assume all sensors synchronized if set to same delay.
            while not self.TOF_Sensor.data_ready: #Delay is Specific to Delay Set by Refresh Rate
                pass
            #Read Data for Each Sensor on Mux with Specified Channel
            self.TOF_Sensor.clear_interrupt()
            self.Distance = self.TOF_Sensor.distance #Update and Log Data Parameter to Global List
            #Log Color Sensor Data
            self.Color = self.Color_Sensor.color_data
            self.Acceleration = self.IMU.acceleration
            self.AngularVelocity = self.IMU.gyro

# ---------------------------------------------------------------------------------------------------------------------------
# All Code Below 'if __name__== "__main__" will NOT execute when the classes above are imported to another file (ex: from xxxx import xxxxx). 
# The code below will thereby only run when the file is run directly (ex: python3 xxxxx.py)
# The code below is used to individually test the color and TOF sensors.
# ---------------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    from adafruit_apds9960.apds9960 import APDS9960
    from adafruit_vl53l4cd import VL53L4CD
    from adafruit_bno055 import BNO055_I2C

    # change the channel number to what you connected to
    apds_channel = 7
    vl53_channel = 1
    bno_channel = 2

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
