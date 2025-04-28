import RPi.GPIO as GPIO
import time
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore   

# Firebase Initialization
cred = credentials.Certificate("solareye_credentials.json")  # Replace with your credentials file
firebase_admin.initialize_app(cred)
db = firestore.client()
control_ref = db.collection('control').document('pir_control')

# GPIO pin for PIR sensor (adjust as needed)
PIR_PIN = 14

# Sensitivity parameters
DELAY_COMPENSATION = 0.5  # Compensation for the inherent delay
PIR_STABILIZATION_TIME = 5  # Time to let PIR sensor stabilize after power-up

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

def get_control_state():
    """Gets the control state from Firestore."""
    try:
        doc = control_ref.get()
        if doc.exists:
            return doc.to_dict().get('enabled', False)
        else:
            print("Control document not found. Assuming disabled.")
            return False
    except Exception as e:
        print(f"Error getting control state: {e}")
        return False

def calibrate_pir_repeat_trigger():
    """Calibrates the PIR sensor in repeat trigger mode, tracking event duration, controlled by Firestore."""

    print("Starting PIR sensor calibration (Repeat Trigger Mode)...")
    print(f"Allow the sensor to stabilize for {PIR_STABILIZATION_TIME} seconds (no movement).")

    # Allow sensor to stabilize
    time.sleep(PIR_STABILIZATION_TIME)

    print("Calibration complete. Monitoring continuous motion...")
    print("Move in front of the sensor to test (continuous motion).")
    print("Press Ctrl+C to exit calibration.")

    motion_start_time = None  # Track when motion started
    motion_end_time = None    #track when motion ended

    try:
        while True:
            enabled = get_control_state()
            if enabled:

                if GPIO.input(PIR_PIN):  # Motion detected
                    if motion_start_time is None:
                        motion_start_time = datetime.now() - timedelta(seconds=DELAY_COMPENSATION)
                        print(f"[{motion_start_time.strftime('%Y-%m-%d %H:%M:%S')}] Continuous Motion detected!")

                else:
                    if motion_start_time is not None : #if motion started and it is now stopped.
                        motion_end_time = datetime.now()
                        duration = motion_end_time - motion_start_time
                        print(f"[{motion_end_time.strftime('%Y-%m-%d %H:%M:%S')}] Continuous motion stopped. Duration: {duration}")
                        motion_start_time = None #reset start time for next event.

                time.sleep(0.1)  # Small delay to avoid repeated messages when no motion
            else:
                print("PIR sensor disabled from Firestore.")
                time.sleep(1) # check firestore every second.

    except KeyboardInterrupt:
        print("Calibration stopped by user.")
    finally:
        GPIO.cleanup()  # Clean up GPIO settings

if __name__ == "__main__":
    calibrate_pir_repeat_trigger()