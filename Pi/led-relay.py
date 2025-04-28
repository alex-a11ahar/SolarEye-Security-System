import RPi.GPIO as GPIO
import time
import firebase_admin
from firebase_admin import credentials, firestore

# GPIO setup
MOSFET_GATE_PIN = 17  # GPIO pin connected to MOSFET Gate
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOSFET_GATE_PIN, GPIO.OUT)
GPIO.output(MOSFET_GATE_PIN, GPIO.LOW)  # Ensure LED is off initially

# Initialize Firebase Admin SDK
cred = credentials.Certificate('solareye_credentials.json')
firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()

# Firestore document reference
doc_ref = db.collection('led-control').document('state')

def update_led(state):
    """Controls the LED based on Firestore boolean state (True/False)."""
    if isinstance(state, bool):  # Ensure state is a boolean
        GPIO.output(MOSFET_GATE_PIN, GPIO.HIGH if state else GPIO.LOW)
        print(f"LED turned {'ON' if state else 'OFF'}.")
    else:
        print("Invalid Firestore state value received.")

# Callback function to handle Firestore document changes
def on_snapshot(doc_snapshot, changes, read_time):
    for doc in doc_snapshot:
        if doc.exists:
            state = doc.to_dict().get('state')  # Expecting True/False
            update_led(state)
        else:
            print("Document does not exist.")

# Watch the Firestore document for real-time updates
doc_watch = doc_ref.on_snapshot(on_snapshot)

try:
    print("Listening for LED control updates from Firestore...")
    while True:
        time.sleep(1)  # Keep script running

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    doc_watch.unsubscribe()  # Unsubscribe from Firestore updates
    GPIO.cleanup()           # Clean up GPIO on exit
    print("Cleaned up GPIO and Firestore listener.")
