import RPi.GPIO as GPIO
import time

RELAY_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)

def turn_on_led():
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    print("LED is ON")

def turn_off_led():
    GPIO.output(RELAY_PIN, GPIO.LOW)
    print("LED is OFF")

try:
    while True:
        command = input("Enter 'on', 'off', or 'exit': ").strip().lower()
        if command == "on":
            turn_on_led()
        elif command == "off":
            turn_off_led()
        elif command == "exit":
            print("Exiting program...")
            break
        else:
            print("Invalid command.")

except KeyboardInterrupt:
    print("\nProgram interrupted.")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Exiting...")