import RPi.GPIO as GPIO
import time
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Initialization
cred = credentials.Certificate("solareye_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
camera_control_ref = db.collection('camera_control').document('camera_state')
led_control_ref = db.collection('led_control').document('led_state')
pir_data_ref = db.collection('pir_sensor_data')

# GPIO pin for PIR sensor (adjust as needed)
PIR_PIN = 14
LED_PIN = 27

# Sensitivity parameters
DELAY_COMPENSATION = 0.5
PIR_STABILIZATION_TIME = 5

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)
GPIO.setup(LED_PIN, GPIO.OUT)

# Ensure LED is off at the start
GPIO.output(LED_PIN, GPIO.LOW)

def get_camera_control_state():
    """Gets the camera control state from Firestore."""
    try:
        doc = camera_control_ref.get()
        if doc.exists:
            return doc.to_dict().get('state', False)
        else:
            print("Camera control document not found. Assuming disabled.")
            return False
    except Exception as e:
        print(f"Error getting camera control state: {e}")
        return False

def get_led_control_state():
    """Gets the LED control state from Firestore."""
    try:
        doc = led_control_ref.get()
        if doc.exists:
            return doc.to_dict().get('state', 0)
        else:
            print("LED control document not found. Assuming off.")
            return 0
    except Exception as e:
        print(f"Error getting LED control state: {e}")
        return 0

def send_pir_event(motion_detected):
    """Sends PIR sensor event data to Firestore."""
    data = {
        'motion_detected': motion_detected,
        'timestamp': datetime.now()
    }
    try:
        pir_data_ref.add(data)
        print(f"PIR event sent to Firestore: {data}")
    except Exception as e:
        print(f"Error sending PIR event to Firestore: {e}")

def calibrate_pir_repeat_trigger():
    """Calibrates the PIR sensor in repeat trigger mode, tracking event duration, controlled by Firestore."""

    print("Starting PIR sensor calibration (Repeat Trigger Mode)...")
    print(f"Allow the sensor to stabilize for {PIR_STABILIZATION_TIME} seconds (no movement).")

    # Allow sensor to stabilize
    time.sleep(PIR_STABILIZATION_TIME)

    print("Calibration complete. Monitoring continuous motion...")
    print("Move in front of the sensor to test (continuous motion).")
    print("Press Ctrl+C to exit calibration.")

    try:
        while True:
            camera_enabled = get_camera_control_state()
            led_enabled = get_led_control_state()

            if camera_enabled:
                if GPIO.input(PIR_PIN):
                    GPIO.output(LED_PIN, GPIO.HIGH)
                    send_pir_event(True) # Motion detected
                else:
                    GPIO.output(LED_PIN, GPIO.LOW)
                    send_pir_event(False) # Motion stopped
                time.sleep(0.1)
            else:
                if led_enabled == 1:
                    GPIO.output(LED_PIN, GPIO.HIGH)
                    time.sleep(0.1)  # Reduced delay for faster strobing
                    GPIO.output(LED_PIN, GPIO.LOW)
                    time.sleep(0.1)  # Reduced delay for faster strobing
                else:
                    GPIO.output(LED_PIN, GPIO.LOW)
                    time.sleep(1)
                print("Camera disabled from Firestore.")

    except KeyboardInterrupt:
        print("Calibration stopped by user.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    calibrate_pir_repeat_trigger()