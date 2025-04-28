import cv2
import time
import firebase_admin
from firebase_admin import credentials, storage, db
import os
import RPi.GPIO as GPIO
import threading

# Set up GPIO for PIR Sensor
PIR_PIN = 18  # Use the GPIO pin connected to your PIR sensor
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

# Firebase Initialization
cred = credentials.Certificate("firebase_credentials.json")  # Update with your Firebase credentials JSON file
firebase_admin.initialize_app(cred, {
    'storageBucket': 'gpiotest.appspot.com'  # Use your Firebase Storage bucket
})

bucket = storage.bucket()

def log_timestamp(event):
    """Logs the timestamp when motion is detected."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Motion {event} at: {timestamp}")
    return timestamp

def capture_and_upload_video():
    try:
        # Start time
        capture_start_time = time.time()

        # Set up video capture
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open video stream.")
            return

        # Set up video writer
        video_filename = "motion_capture_test.avi"
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))
        
        # Capture 30 seconds of video
        print("Starting video capture...")
        start_time = time.time()
        while int(time.time() - start_time) < 30:
            ret, frame = cap.read()
            if ret:
                out.write(frame)
            else:
                break

        # Release resources
        cap.release()
        out.release()
        print("Video capture completed.")
        
        # Start time for Firebase upload
        upload_start_time = time.time()

        # Upload video to Firebase Storage
        blob = bucket.blob(video_filename)
        blob.upload_from_filename(video_filename)
        blob.make_public()  # Optional: make public if you want a public URL
        
        # End time for Firebase upload
        upload_end_time = time.time()
        upload_duration = upload_end_time - upload_start_time
        print(f"Firebase upload duration: {upload_duration:.4f} seconds")

        # Clean up local video file after upload
        os.remove(video_filename)
        print("Video file uploaded to Firebase.")

    except Exception as e:
        print("Error during capture or Firebase upload:", e)

def motion_detected():
    log_timestamp("detected")
    video_thread = threading.Thread(target=capture_and_upload_video)
    video_thread.start()

try:
    print("Waiting for motion...")
    while True:
        if GPIO.input(PIR_PIN):
            print("Motion detected!")
            motion_detected()
            time.sleep(2)  # Prevent multiple triggers in quick succession

except KeyboardInterrupt:
    print("Exiting program")

finally:
    GPIO.cleanup()
