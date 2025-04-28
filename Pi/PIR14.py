from gpiozero import MotionSensor
from time import sleep
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Firebase Initialization
cred = credentials.Certificate("solareye_credentials.json")  # Update with your Firebase credentials JSON file
firebase_admin.initialize_app(cred)

# Reference to Firestore database location
db = firestore.client()  # Initialize Firestore client
pir_sensor_ref = db.collection('pir_sensor_data')  # Reference to Firestore collection

pir = MotionSensor(14)  # Replace 17 with the GPIO pin you connected OUT to

while True:
    if pir.motion_detected:
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        data = {
            'motion_detected': True,
            'timestamp': timestamp,
        }

        try:
            pir_sensor_ref.add(data)
            print(f"Motion detected! Data sent to Firestore: {timestamp}")
        except Exception as e:
            print(f"Error sending data to Firestore: {e}")

        sleep(1)  # Avoid rapid repeated detections
    else:
        print("No motion")
        sleep(1)