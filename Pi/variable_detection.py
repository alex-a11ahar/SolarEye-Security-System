import time
import os
import subprocess
import threading
import firebase_admin
from firebase_admin import credentials, firestore, storage
from gpiozero import MotionSensor
import sys

# Firebase Initialization
try:
    cred = credentials.Certificate("solareye_credentials.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': "solareye-security-system.firebasestorage.app"  # Replace with your Firebase Storage bucket
    })
    db = firestore.client()
    bucket = storage.bucket()
    pir_sensor_ref = db.collection('pir_sensor_data')
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    sys.exit(1)

# PIR Sensor setup
try:
    pir = MotionSensor(14)
except Exception as e:
    print(f"Error initializing PIR sensor: {e}")
    sys.exit(1)

# Globals
recording_process = None
recording_filename = None
recording_lock = threading.Lock()

def log_timestamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def upload_video(file_path):
    blob = bucket.blob(f"motion_videos/{os.path.basename(file_path)}")
    blob.upload_from_filename(file_path)
    print(f"Uploaded {file_path} to Firebase Storage.")
    os.remove(file_path)  # Optional: delete local file after upload

def start_recording():
    global recording_process, recording_filename
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    recording_filename = f"/tmp/motion_{timestamp}.h264"
    print(f"[{timestamp}] Starting recording...")

    command = [
        "libcamera-vid",
        "-t", "0",  # Run indefinitely until killed
        "--width", "640",
        "--height", "480",
        "--framerate", "24",
        "--output", recording_filename
    ]

    recording_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def stop_recording():
    global recording_process, recording_filename
    if recording_process:
        recording_process.terminate()
        recording_process.wait()
        recording_process = None
        print(f"Stopped recording: {recording_filename}")
        upload_video(recording_filename)

def motion_function():
    timestamp = log_timestamp()
    data = {'motion': 'detected', 'timestamp': timestamp}
    try:
        pir_sensor_ref.add(data)
        print(f"[{timestamp}] Motion detected. Data pushed to Firestore.")
    except Exception as e:
        print(f"[{timestamp}] Failed to send motion data to Firestore: {e}")

    with recording_lock:
        if recording_process is None:
            start_recording()

def no_motion_function():
    timestamp = log_timestamp()
    data = {'motion': 'stopped', 'timestamp': timestamp}
    try:
        pir_sensor_ref.add(data)
        print(f"[{timestamp}] Motion stopped. Data pushed to Firestore.")
    except Exception as e:
        print(f"[{timestamp}] Failed to send motion stop data to Firestore: {e}")

    with recording_lock:
        if recording_process:
            stop_recording()
            time.sleep(1)  # Prevent overlapping triggers

# Assign event handlers
pir.when_motion = motion_function
pir.when_no_motion = no_motion_function

print("Monitoring PIR sensor for motion...")
print("Type 'exit' and press Enter to terminate.")

try:
    while True:
        user_input = input().strip().lower()
        if user_input == "exit":
            print("Exiting program.")
            with recording_lock:
                if recording_process:
                    stop_recording()
            sys.exit(0)
except KeyboardInterrupt:
    print("Program interrupted.")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    with recording_lock:
        if recording_process:
            stop_recording()
    print("Program exiting.")