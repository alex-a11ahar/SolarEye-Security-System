import cv2
import os
import time
import firebase_admin
from firebase_admin import credentials, db, storage
from gpiozero import MotionSensor
from signal import pause

# Firebase Initialization
cred = credentials.Certificate("firebase_credentials.json")  # Update with your Firebase credentials JSON file
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://gpiotest-default-rtdb.firebaseio.com/',  # Replace with your Firebase database URL
    'storageBucket': 'gpiotest.appspot.com'  # Use your Firebase Storage bucket
})

# Reference to Firebase Realtime Database location
ref = db.reference('pir_sensor_data')

# PIR Sensor setup
pir = MotionSensor(18)  # GPIO pin where PIR sensor is connected

# Define the output directories
output_dir_video = 'videos'
output_dir_frames = 'extracted_frames'
output_dir_preprocessed = 'preprocessed_frames'

# Ensure directories exist
os.makedirs(output_dir_video, exist_ok=True)
os.makedirs(output_dir_frames, exist_ok=True)
os.makedirs(output_dir_preprocessed, exist_ok=True)

# Global variable to manage motion detection state
motion_detected = False
video_capturing = False  # New variable to check if video is currently capturing

def capture_video():
    global video_capturing
    video_capturing = True  # Set to True to indicate video capture has started

    # Video capture from USB camera
    camera_index = 0
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Define output video file path with a unique timestamp
    output_filename = os.path.join(output_dir_video, f'output_{time.strftime("%Y%m%d_%H%M%S")}.avi')
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_filename, fourcc, 20.0, (640, 480))

    # Continue capturing video until motion stops
    while motion_detected:
        ret, frame = cap.read()
        if ret:
            out.write(frame)
        else:
            break

    # Release everything
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    video_capturing = False  # Reset video capturing state

    # Check if the video file was created successfully
    if os.path.exists(output_filename):
        # Upload video to Firebase Storage
        upload_video_to_firebase(output_filename)
        # Extract and preprocess frames from the video
        extract_and_preprocess_frames(output_filename)
    else:
        print("Error: Video file was not created.")

def upload_video_to_firebase(video_path):
    bucket = storage.bucket()
    video_filename = os.path.basename(video_path)
    blob = bucket.blob(f'videos/{video_filename}')
    blob.upload_from_filename(video_path)
    blob.make_public()
    print(f'Video uploaded to Firebase with URL: {blob.public_url}')

def extract_and_preprocess_frames(video_path):
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    max_frames = 250  # Limit to 250 frames

    # Clear existing frames before extraction
    for folder in [output_dir_frames, output_dir_preprocessed]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        # Save raw frame to extracted_frames folder
        frame_filename = os.path.join(output_dir_frames, f'frame_{frame_count:04d}.jpg')
        cv2.imwrite(frame_filename, frame)

        # Preprocess and save frame
        preprocessed_frame = preprocess_frame(frame)
        preprocessed_filename = os.path.join(output_dir_preprocessed, f'frame_{frame_count:04d}.jpg')
        cv2.imwrite(preprocessed_filename, preprocessed_frame)

        frame_count += 1

    cap.release()
    print(f'Extracted and preprocessed {frame_count} frames to {output_dir_frames} and {output_dir_preprocessed}')

def preprocess_frame(frame):
    frame_resized = cv2.resize(frame, (640, 480))
    frame_gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
    frame_normalized = frame_gray / 255.0  # Scale pixel values to [0, 1]
    return (frame_normalized * 255).astype('uint8')  # Convert back to uint8 for saving

def motion_function():
    global motion_detected
    if not motion_detected:  # Check if motion is already detected
        data = {
            'motion': 'detected',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        ref.push(data)
        print("Motion detected and data pushed to Firebase")

        motion_detected = True  # Set motion detected state
        capture_video()  # Start video capture when motion is detected

def no_motion_function():
    global motion_detected
    if motion_detected:
        data = {
            'motion': 'stopped',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        ref.push(data)
        print("Motion stopped and data pushed to Firebase")

        motion_detected = False  # Set motion detected state to False

# Assign functions to motion events
pir.when_motion = motion_function
pir.when_no_motion = no_motion_function

print("Monitoring GPIO pin for sensor activation...")
pause()
