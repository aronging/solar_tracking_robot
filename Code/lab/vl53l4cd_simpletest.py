# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2022 Carter Nelson for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 Carter Nelson for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

# Simple demo of the VL53L4CD distance sensor.
# Will print the sensed range/distance every second.

import board

from adafruit_vl53l4cd import VL53L4CD
from adafruit_tca9548a import TCA9548A

i2c = board.I2C()  # uses board.SCL and board.SDA
tca = TCA9548A(i2c)

vl53 = VL53L4CD(tca[1], 0x29)

# OPTIONAL: can set non-default values
vl53.inter_measurement = 0
vl53.timing_budget = 200

print("VL53L4CD Simple Test.")
print("--------------------")
model_id, module_type = vl53.model_info
print(f"Model ID: 0x{model_id:0X}")
print(f"Module Type: 0x{module_type:0X}")
print(f"Timing Budget: {vl53.timing_budget}")
print(f"Inter-Measurement: {vl53.inter_measurement}")
print("--------------------")

vl53.start_ranging()

while True:
    while not vl53.data_ready:
        pass
    vl53.clear_interrupt()
    print(f"Distance: {vl53.distance} cm")