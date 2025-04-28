from gpiozero import MotionSensor
from time import sleep
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Firebase Initialization
cred = credentials.Certificate("solareye_credentials.json")
firebase_admin.initialize_app(cred)

# Firestore setup
db = firestore.client()
pir_sensor_ref = db.collection('pir_sensor_data')
control_ref = db.collection('control').document('pir_control')

pir = MotionSensor(14)

def get_control_state():
    try:
        doc = control_ref.get()
        if doc.exists:
            return doc.to_dict().get('state', False) # changed to 'state'
        else:
            print("Control document not found. Assuming disabled.")
            return False
    except Exception as e:
        print(f"Error getting control state: {e}")
        return False

while True:
    state = get_control_state() # changed enabled to state

    if state: # changed enabled to state
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

            sleep(1)
        else:
            print("No motion")
            sleep(1)
    else:
        print("PIR sensor disabled from Firestore.")
        sleep(1) # check firestore state every second
        # Optionally, you can add code here to turn off the GPIO pin if needed.
        # However, gpiozero handles the input pin, and it will not output anything.
        # So it is not really necessary to turn the pin off.
        # If you were using the pin as output, then it would be.