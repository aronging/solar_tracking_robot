from gpiozero import RotaryEncoder
import time

# Initialize the encoder and button (adjust pin numbers as needed)
# Using BCM pin numbering
left_encoder = RotaryEncoder(a=17, b=18, max_steps=0)
right_encoder = RotaryEncoder(a=23, b=22, max_steps=0)

step_per_rev = 28 * 2 # from the specification of the motor

# Main loop to print the encoder value
while True:
    # Left encoder: positive is forward; Right encoder: negative is forward
    print(f"left encoder: {left_encoder.steps/step_per_rev}, right encoder: {-right_encoder.steps/step_per_rev}")
    time.sleep(0.1) # Add a small delay to avoid swamping the CPU with print statements