# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time

import board

from adafruit_apds9960.apds9960 import APDS9960
from adafruit_tca9548a import TCA9548A

i2c = board.I2C()  # uses board.SCL and board.SDA
tca = TCA9548A(i2c)
apds = APDS9960(tca[7])

apds.enable_proximity = True
apds.enable_color = True

while True:
    print("Proximity: ", apds.proximity)
    print("Color: ", apds.color_data)
    time.sleep(0.2)