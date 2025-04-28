import RPi.GPIO as GPIO
import time
import os

# Define the GPIO pin used by the sensor (adjust as needed)
SENSOR_PIN = 18

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Using pull-down resistor

# Define the motion service start and stop functions
def start_motion():
    # Start the motion service
    os.system("sudo systemctl start motion")
    print("Motion started, video streaming enabled.")
    print("Live stream URL: http://<raspberry_pi_ip>:8081")  # Replace with the actual IP of your Raspberry Pi

def stop_motion():
    # Stop the motion service
    os.system("sudo systemctl stop motion")
    print("Motion stopped, video streaming disabled.")

def wait_for_no_motion():
    # Wait for 5 seconds with no motion detection before stopping the stream
    print("Waiting for 5 seconds to detect no motion...")
    time.sleep(5)
    return GPIO.input(SENSOR_PIN) == GPIO.LOW  # Return True if no motion was detected

try:
    print("Waiting for GPIO sensor activation...")
    while True:
        # Wait for sensor to be triggered
        if GPIO.input(SENSOR_PIN) == GPIO.HIGH:
            print("Sensor activated!")
            start_motion()  # Start video stream

            # Wait for sensor to be deactivated (e.g., button released)
            while GPIO.input(SENSOR_PIN) == GPIO.HIGH:
                time.sleep(0.1)  # Polling the sensor state

            # Wait for 5 seconds before stopping the stream if no motion detected
            if wait_for_no_motion():
                stop_motion()  # Stop video stream if no motion was detected after 5 seconds

        time.sleep(0.1)

except KeyboardInterrupt:
    print("Program interrupted.")
finally:
    GPIO.cleanup()  # Clean up GPIO settings
