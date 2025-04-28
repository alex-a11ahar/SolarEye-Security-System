from gpiozero import DigitalOutputDevice, LED
from time import sleep
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Firebase Initialization
cred = credentials.Certificate("solareye_credentials.json")
firebase_admin.initialize_app(cred)

# Firestore setup
db = firestore.client()

# LED Control
led_ref = db.collection('control').document('led_control')
led_pin = 27  # GPIO pin for LED
led = LED(led_pin)

def get_led_state():
    try:
        doc = led_ref.get()
        if doc.exists:
            return doc.to_dict().get('state', False)
        else:
            print("LED control document not found. Assuming OFF.")
            return False
    except Exception as e:
        print(f"Error getting LED state: {e}")
        return False

# Intake Fan Control
fan_ref = db.collection('control').document('intake_control')
fan_pin =  17 # GPIO pin for Fan
fan = DigitalOutputDevice(fan_pin)

def get_fan_state():
    try:
        doc = fan_ref.get()
        if doc.exists:
            return doc.to_dict().get('state', False)
        else:
            print("Fan control document not found. Assuming OFF.")
            return False
    except Exception as e:
        print(f"Error getting Fan state: {e}")
        return False

# Outake Fan Control
camera_ref = db.collection('control').document('outtake_control')
camera_pin = 22 # GPIO pin for Camera (example, might need more complex control)
camera = DigitalOutputDevice(camera_pin) # Assuming simple on/off for camera

def get_camera_state():
    try:
        doc = camera_ref.get()
        if doc.exists:
            return doc.to_dict().get('state', False)
        else:
            print("Camera control document not found. Assuming OFF.")
            return False
    except Exception as e:
        print(f"Error getting Camera state: {e}")
        return False

while True:
    # Control LED
    led_state = get_led_state()
    if led_state:
        led.on()
        print("LED turned ON")
    else:
        led.off()
        print("LED turned OFF")

    # Control Fan
    fan_state = get_fan_state()
    if fan_state:
        fan.on()
        print("Intake Fan turned ON")
    else:
        fan.off()
        print("Intake Fan turned OFF")

    # Control Camera
    camera_state = get_camera_state()
    if camera_state:
        camera.on()
        print("Outtake turned ON")
        # Add camera specific actions here if needed
    else:
        camera.off()
        print("Outtake turned OFF")
        # Add camera specific actions here if needed

    sleep(1) # Check control states every second