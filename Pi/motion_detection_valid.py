import time
import os
import subprocess
import threading
import firebase_admin
from firebase_admin import credentials, firestore, storage
from gpiozero import MotionSensor, LED
import sys

# Firebase Initialization
try:
    cred = credentials.Certificate("solareye_credentials.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': "solareye-security-system.firebasestorage.app"
    })
    db = firestore.client()
    bucket = storage.bucket()
    video_sensor_ref = db.collection('video_sensor_data')
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    sys.exit(1)

# PIR Sensor setup
try:
    pir = MotionSensor(14)
except Exception as e:
    print(f"Error initializing PIR sensor: {e}")
    sys.exit(1)

# LED setup (GPIO 17)
led = LED(17)

# Globals
recording_process = None
recording_filename_h264 = None
recording_filename_mp4 = None
recording_lock = threading.Lock()

def log_timestamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def generate_video_url(filename):
    return f"https://storage.googleapis.com/solareye-security-system.firebasestorage.app/videos/{filename}"

def convert_to_mp4(input_path, output_path):
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-framerate", "24",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            output_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Converted {input_path} to {output_path}")
    except Exception as e:
        print(f"Failed to convert to MP4: {e}")

def upload_video(file_path, timestamp_str):
    base_name = os.path.basename(file_path)
    blob = bucket.blob(f"videos/{base_name}")
    
    try:
        blob.upload_from_filename(file_path)
        blob.make_public()
        video_url = blob.public_url
        print(f"Uploaded {file_path} to Firebase Storage.")
    except Exception as e:
        print(f"Upload failed: {e}")
        video_url = generate_video_url(base_name)  # Fallback

    # Push metadata to Firestore
    data = {
        'video_url': video_url,
        'timestamp': timestamp_str
    }
    try:
        video_sensor_ref.add(data)
        print(f"Metadata sent to Firestore: {data}")
    except Exception as e:
        print(f"Failed to send video metadata to Firestore: {e}")

    os.remove(file_path)

def start_recording():
    global recording_process, recording_filename_h264, recording_filename_mp4
    timestamp_filename = time.strftime('%Y%m%d_%H%M%S')
    recording_filename_h264 = f"/tmp/video_{timestamp_filename}.h264"
    recording_filename_mp4 = f"/tmp/video_{timestamp_filename}.mp4"

    print(f"[{timestamp_filename}] Starting recording...")

    command = [
        "libcamera-vid",
        "-t", "0",
        "--width", "1280",
        "--height", "720",
        "--framerate", "24",
        "--roi", "0.0,0.0,1.0,1.0",  # full sensor area
        "--output", recording_filename_h264
    ]

    recording_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def stop_recording():
    global recording_process, recording_filename_h264, recording_filename_mp4
    if recording_process:
        recording_process.terminate()
        recording_process.wait()
        recording_process = None
        print(f"Stopped recording: {recording_filename_h264}")

        convert_to_mp4(recording_filename_h264, recording_filename_mp4)
        timestamp_str = log_timestamp()
        upload_video(recording_filename_mp4, timestamp_str)

        # Clean up .h264 file
        if os.path.exists(recording_filename_h264):
            os.remove(recording_filename_h264)

def motion_function():
    timestamp = log_timestamp()
    print(f"[{timestamp}] Motion detected.")
    led.on()

    with recording_lock:
        if recording_process is None:
            start_recording()

def no_motion_function():
    timestamp = log_timestamp()
    print(f"[{timestamp}] Motion stopped.")
    led.off()

    with recording_lock:
        if recording_process:
            stop_recording()
            time.sleep(1)

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
    led.off()
    print("Program exiting.")
