import board
import busio
import adafruit_tca9548a # For TCA954x Muxes

# Main I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Mux setup (replace with your Mux's address & pins)
mux_address = 0x70 # Example Mux address
# Assuming channel pins for TCA954x are on GPIO 17, 27, 22 (BCM)
# Check your Mux's datasheet!
tca = adafruit_tca9548a.TCA9548A(i2c, address=mux_address)

print("Scanning for sensors on Mux Channels:")
for channel in range(8):
    if tca[channel].try_lock():
        print(f"Channel {channel}:", end="")
        addresses = tca[channel].scan()
        print([hex(address) for address in addresses if address != 0x70])
        tca[channel].unlock()
