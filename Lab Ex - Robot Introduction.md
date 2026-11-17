# Lab Ex – Robot Introduction

**Texas A&M University**
**Multidisciplinary Engineering Technology**
**MXET-345: Numerical Methods in Robotics Applications**

> Transcribed from `Lab Ex - Robot Introduction (1).pdf` (7 pages). Text is verbatim; hyperlinks embedded in the PDF are preserved as Markdown links. Figures are described in *[Figure: …]* notes, since the images themselves are not reproduced.

---

## Overview

In this lab we will introduce the robot to be used for your final project. This robot is controlled by two motors and two servos, and it is capable of locomotion tasks and ready for modifications based on what you need. We will demonstrate how to connect to the Raspberry Pi on the robot and operate the robot using simple Python scripts.

## Software Needed

- [Visual Studio Code](https://code.visualstudio.com/download)

## Connect to the Raspberry Pi via Visual Studio Code

1. Download Visual Studio Code, run the installer, and follow its instructions.
2. Once installation is complete you will need to install the extensions.
   a. Select the "extensions" tab from the toolbar on the left.
   b. Search "python" and select the Python extension from Microsoft. This extension allows VS Code to interpret and highlight Python along with some other useful features. Install the extension.

   > *[Figure 1: Installing Visual Studio Code Extensions — screenshot of the VS Code Extensions panel.]*

   c. Next, search for the "remote SSH" extension. Select and install the first option, which should be "Remote - SSH" from Microsoft.
   d. Once installation is complete, restart your VS Code client.
3. While you wait, connect your laptop to the lab's wireless network.
   a. This network is hidden and will not appear in the list of nearby Wi-Fi networks. Instead, select the "Hidden" option.
   b. For the SSID, enter "mxet_Lab" and for the password enter "mxetlab006".
   c. This is necessary to connect to your Pi through a shared network for use in headless mode.
4. Now turn on your robot controller and connect to the Pi using remote SSH.
   a. First, switch to the "Remote Explorer" tab by clicking a monitor icon on the left side. Click the plus icon besides "SSH". It should look like the figure below. Then enter "`ssh pi@192.168.1.2xx`", where xx is your team number on your board. Next, select the user SSH configuration file to update. The file name should contain your laptop's host name and "/.ssh/config". Hit connect button add the bottom right corner of the VS Code window.

   > *[Figure 2: add new host to Remote Explorer — screenshot of the Remote Explorer "SSH" section with the "+" (New Remote) button.]*

   b. Now, a new window would pop up. Select the platform, Linux. Enter your Raspberry Pi password, "mxet". It would take about 5 minutes to load the VS Code remote server to your Raspberry Pi.
   c. Once complete, your VS Code client will connect to your Raspberry Pi. After this connection completes you can read or write files remotely as well as interpret and highlight Python syntax.
   d. If the connection failed due to the connection time out, [try this solution](https://stackoverflow.com/questions/59978826/why-ssh-connection-timed-out-in-vscode). Open your settings in your Preferences tab > Settings. Search for "useLocalServer" and disable this setting.
      `"remote.SSH.useLocalServer": false`

## Operate the Robot by Python Scripts

1. In your VS code, open the terminal with Ctrl + \`. Activate a Python virtual environment that we have already set up for you by `source ~/env/bin/activate`. You need to do this every time you start a connection before running a python script, since the python packages are downloaded in the virtual environment.
2. Then create a new directory by `mkdir mxet345_project`. Move into the directory by `cd mxet345_project`.
3. To add "mxet345_project" folder to your host, go to the Remote Explorer and click the folder-plus icon which should said "Connect in New Window…" when your cursor hovers above the icon. Enter the password in the new window. In the Explorer, click Open Folder button, enter the path, "/home/pi/mxet345_project", and hit enter. Enter the password again after the window is reloaded. Now, go to the Remote Explorer and refresh the remotes like figure 8. You should see "mxet345_project" folder under your host.

   > *[Figure 3: Add mxet345_project folder in Remote Explorer — host "192.168.1.198 connected", folder "mxet345_project /home/pi…", with the "Connect in New Window…" tooltip.]*
   >
   > *[Figure 4: Open folder with the path, "/home/pi/mxet345_project" — Explorer panel showing "Connected to remote." and the "Open Folder" button.]*
   >
   > *[Figure 5: Refresh your remote explorer and check if mxet345_project folder shows up — "REMOTES (TUNNELS/SSH)" panel with the Refresh button.]*

4. In terminal, create a new script by `touch motor_servo_pwm.py`. Then refresh your remote explorer and click to edit the file. Copy the code `motor_servo_pwm.py` you downloaded from Canvas to this file and save the file. Do the same thing for other provided python files. Alternatively, you can download the files to your computer and drag them to the folder in VS Code.
   Note: If the motor controller address is not 0x40, you need to change following line in the script to the correct address: `self.pca = PCA9685(i2c_bus, address= 0x40)`
5. Check the [motor controller](https://learn.adafruit.com/adafruit-16-channel-pwm-servo-hat-for-raspberry-pi/overview) to understand how to control the [motors](https://docs.revrobotics.com/duo-build/motion/motors/hd-hex-motor). The controller can output PWM signals to 16 channels for controlling different motors. Below is the photo of the motor controller we are using.

   > *[Figure 6: Photo of the motor controller — Adafruit "16 x 12-bit PWM Servo/PWM Pi HAT!" (PCA9685 chip) mounted on a Raspberry Pi. Visible: 5–6 VDC barrel jack and +5/GND screw terminal for servo power, I2C address jumpers (A0–A5), prototyping area, and four groups of 3-pin headers (S / V+ / G) outlined in red and labelled "Channels".]*

6. Connect the motor power cable to the connectors on the board, and connect the servo motor cables to any free channels on the motor controller, based on the photo below.

   > *[Figure 7: Connection for Motors and Servos — top view of the robot's electronics deck. Red box at the PWM HAT headers labelled "To Servos"; red box around the red/black power connectors at the bottom edge of the deck labelled "To Motors". Also visible: Raspberry Pi in a case under the PWM HAT, a rocker power switch, blue screw-terminal distribution strips, three small green driver boards, and a "CPT" DC-DC converter module.]*

7. Check the script named `test_motor.py`, understand how it imports the provided script and uses it to control the DC motors and servo motors. **Change the channel numbers in this script to the channels you have connected for DC motors and servo motors.**
8. In order to make VS code identify the virtual environment, first go to extensions and install Python and Pylance locally. Then press Ctrl + Shift + P and go to `Python: Select Interpreter`. Select "`Enter interpreter path`", click "`Find`", and input "`/home/pi/env/bin/python`".

   > *[Figure 8: Ctrl + Shift + P and go to "Python: Select Interpreter".]*
   >
   > *[Figure 9: Choose "Enter interpreter path" — options shown: "Create Virtual Environment…", "Enter interpreter path…"; current selection "~/env/bin/python".]*
   >
   > *[Figure 10: Click "Find" and enter the path of the virtual environment.]*

9. Before running the script, make sure to place the robot off ground. Run the script by `python3 test_motor.py`. You should see the motors and servos running.
10. Optional practice: Measure the distance between two wheels and the diameter of the wheels, then together with the [specifications of the motor](https://docs.revrobotics.com/duo-build/motion/motors/hd-hex-motor), create a program `inverse_kinematics.py` which uses robot forward velocity (m/s) and rotational speed (rad/s) as inputs to control the two motors. Test the program with only forward velocity or only rotational speed to check if robot moves as expected. This will be helpful when you build your final project later.

## Access the Sensors Readings by Python Scripts

1. Understand and connect the sensors based on the photo below. We connect PI and [SparkFun MUX](https://docs.circuitpython.org/projects/tca9548a/en/latest/) via the Qwiic connector communicated by I2C. MUX has 8 channels in total which can be connected to 8 different sensors.
   The sensors we provided:
   - Adafruit [VL53L4CD](https://docs.circuitpython.org/projects/vl53l4cd/en/latest/) Time of Flight Distance Sensor
   - Adafruit [APDS9960](https://docs.circuitpython.org/projects/apds9960/en/latest/) Proximity, Light, RGB, and Gesture Sensor
   - Adafruit [BNO055](https://docs.circuitpython.org/projects/bno055/en/latest/) 9-DOF Absolute Orientation IMU Fusion Breakout
   - [Encoders](https://docs.revrobotics.com/duo-control/sensors/encoders/motor-based-encoders)
2. Connect the sensors (except encoders) to different channels of MUX. When connected, the LED on the sensor should be on. If some channels don't work, try using another channel.
3. Download the python scripts on Canvas using the same way as the last section.
4. Check the script named `test_sensor.py`, understand how it imports the provided scripts and uses them to read the sensor data. **Change the channel numbers in this script to the channels you are using.**

   > *[Figure 11: Sensor Connections — red boxes label "Sensor" (a small breakout on a pink printed mount), "MUX (8 Channels)" (red SparkFun Qwiic mux board on a blue printed mount), and "Qwiic on PI" (Qwiic connector on the PWM HAT). Qwiic cables run Pi → MUX → sensor.]*

5. Read the script named `sensor_module.py`, understand how it creates a new thread to read and save the sensor data in class **Sensor_Thread**. If your final project needs additional sensor data, you need to add new attributes in **`__init__`** and assign the attributes in **`_read_data`**. You can find additional information in the test script we provided for each sensor, and in the documentation of the sensors through the link in step 1.
6. Run the script by `python3 test_sensor.py`. You should see the sensor data displayed in the terminal.
7. Power off your PI, remove the motor controller board on top of the PI and connect the encoders based on the photo below (color of the cables should match). Then place the board back.

   > *[Figure 12: Encoder Connections — GPIO screw-terminal breakout board ("xikentec.com HDD40 Ver. 1.0") on the Pi. Red boxes label "Left Encoder" and "Right Encoder", each a group of four terminals (red / black / two signal wires) on the 3.3V/GND/GPIO rows.]*

8. Check the script `test_encoder.py` and understand how it receives encoder data. We are using [RotaryEncoder](https://gpiozero.readthedocs.io/en/stable/api_input.html#rotaryencoder) class in [gpiozero](https://gpiozero.readthedocs.io/en/stable/index.html) package to read the encoder data.
9. Run the script by `python3 test_encoder.py`. Rotate the wheels by hand and you should see the encoder readings displayed in the terminal.
10. Optional practice: Create a new script `forward_kinematics.py` that transforms the encoder readings to the motor velocity (rev/s), then to the actual forward velocity (m/s) and rotational speed (rad/s) of the robot. Display the values on terminal. This will be helpful when you build your final project later.

## Guidelines for the Final Project

1. You shouldn't disassemble the robot. You can only add parts to the original robot.
2. Make a list of parts you need for your final project after your proposal and give it to your TA.
3. Always backup your files (download on your computer or save in cloud service) after each lab.
4. Some ideas you can use for the final project:
   a. Inverse kinematics: Numerical methods like the Newton-Raphson method are used to solve the joint angles needed to reach a specific end-effector position.
   b. Trajectory generation: Numerical methods, such as Lagrange polynomial interpolation, are used to generate smooth, efficient paths for robotic arms and mobile robots.
   c. Sensor-based control: Numerical integration (e.g., Trapezoidal rule) is used to calculate a robot's speed and position from sensor readings to enable real-time control.
   d. Control Systems: Proportional-Integral-Derivative (PID) controllers, which rely on numerical calculations of error over time, are implemented to ensure the motors achieve and maintain the desired wheel speeds accurately.

---

*Pages 1–7 of 7*
