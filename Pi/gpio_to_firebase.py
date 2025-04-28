from gpiozero import MotionSensor
from signal import pause
import firebase_admin
from firebase_admin import credentials, db
import time

# Firebase Initialization
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://gpiotest-default-rtdb.firebaseio.com/'  # Replace with your Firebase database URL
})

# Reference to Firebase Realtime Database location
ref = db.reference('pir_sensor_data')

# PIR Sensor setup
pir = MotionSensor(18)  # GPIO pin where PIR sensor is connected

# Functions to handle motion events and push data to Firebase
def motion_function():
    data = {
        'motion': 'detected',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    ref.push(data)
    print("Motion detected and data pushed to Firebase")

def no_motion_function():
    data = {
        'motion': 'stopped',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    ref.push(data)
    print("Motion stopped and data pushed to Firebase")

# Assign functions to motion events
pir.when_motion = motion_function
pir.when_no_motion = no_motion_function

# Wait for PIR sensor events
pause()
