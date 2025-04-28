import RPi.GPIO as GPIO
import time

# Define GPIO pins
MOSFET_GATE_PIN = 17  # Controls fan power (on/off)
PWM_PIN = 18          # Controls fan speed (PWM signal)

# Setup GPIO mode and pins
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOSFET_GATE_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

# Initially, power off the fan and set PWM duty cycle to 0%
GPIO.output(MOSFET_GATE_PIN, GPIO.LOW)
frequency = 250  # PWM frequency in Hz (adjust as needed for your fan)
pwm = GPIO.PWM(PWM_PIN, frequency)
pwm.start(0)

print("Enter 'on' to turn on the fan, 'off' to turn it off, 'speed <0-100>' to set fan speed, or 'exit' to quit.")

try:
    while True:
        command = input("Command: ").strip().lower()

        if command == "on":
            # Turn on the fan by enabling power via MOSFET
            GPIO.output(MOSFET_GATE_PIN, GPIO.HIGH)
            print("Fan turned ON.")

        elif command == "off":
            # Turn off the fan by cutting power and setting PWM duty cycle to 0
            GPIO.output(MOSFET_GATE_PIN, GPIO.LOW)
            pwm.ChangeDutyCycle(0)
            print("Fan turned OFF.")

        elif command.startswith("speed"):
            # Command should be in the form "speed <value>"
            try:
                parts = command.split()
                if len(parts) != 2:
                    raise ValueError("Invalid format")
                speed = float(parts[1])
                if speed < 0 or speed > 100:
                    print("Speed value must be between 0 and 100.")
                else:
                    # Set PWM duty cycle to adjust fan speed
                    pwm.ChangeDutyCycle(speed)
                    print(f"Fan speed set to {speed}% duty cycle.")
            except Exception as e:
                print("Usage: speed <value>  (where <value> is a number between 0 and 100)")

        elif command == "exit":
            break

        else:
            print("Invalid command. Use 'on', 'off', 'speed <value>', or 'exit'.")

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    pwm.stop()           # Stop PWM output
    GPIO.cleanup()       # Clean up GPIO settings
    print("GPIO cleaned up.")
