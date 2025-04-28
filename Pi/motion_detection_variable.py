import cv2
import os
import time
import firebase_admin
from firebase_admin import credentials, db, storage
from gpiozero import MotionSensor
from signal import pause
import os  # Make sure os is imported
import sys

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

# Define output directories
output_dir_video = 'videos'
output_dir_frames = 'extracted_frames'
output_dir_preprocessed = 'preprocessed_frames'
output_dir_images = 'motion_images'

# Ensure directories exist
os.makedirs(output_dir_video, exist_ok=True)
os.makedirs(output_dir_frames, exist_ok=True)
os.makedirs(output_dir_preprocessed, exist_ok=True)
os.makedirs(output_dir_images, exist_ok=True)

# Global variables
motion_detected = False
continuous_mode = False  # Tracks whether continuous mode is enabled
last_motion_time = None  # Tracks when motion was last detected

def initial_capture():
    """Captures a single image and uploads it to Firebase Storage."""
    camera_index = 0
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("Error: Could not open camera for initial capture.")
        return

    ret, frame = cap.read()
    if ret:
        image_path = os.path.join(output_dir_images, f'motion_image_{time.strftime("%Y%m%d_%H%M%S")}.jpg')
        cv2.imwrite(image_path, frame)
        upload_image_to_firebase(image_path)
    else:
        print("Error: Could not capture image.")
    cap.release()

def upload_image_to_firebase(image_path):
    bucket = storage.bucket()
    image_filename = os.path.basename(image_path)
    blob = bucket.blob(f'images/{image_filename}')
    blob.upload_from_filename(image_path)
    blob.make_public()
    print(f'Image uploaded to Firebase with URL: {blob.public_url}')

def detect_motion_in_frame(frame, previous_frame):
    """
    Detects motion by comparing the current frame with the previous frame.
    Returns True if motion is detected, False otherwise.
    """
    if previous_frame is None:
        return False

    # Convert frames to grayscale
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_prev_frame = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)

    # Compute absolute difference between frames
    diff = cv2.absdiff(gray_prev_frame, gray_frame)

    # Threshold the difference to identify motion areas
    _, threshold = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    motion_area = cv2.countNonZero(threshold)

    # Define a minimum motion area to detect motion
    min_motion_area = 5000  # Adjust this value as needed

    return motion_area > min_motion_area

def capture_video():
    """Captures video and stops after no motion is detected for 5 seconds."""
    global motion_detected, last_motion_time
    motion_detected = True  # Set motion_detected to True when video capture starts

    # Video capture from USB camera
    camera_index = 0
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Set camera parameters for better low-light capture (optional)
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)  # Adjust exposure for low light (experiment with value)
    cap.set(cv2.CAP_PROP_GAIN, 0.5)  # Adjust gain to improve brightness in low light (adjust as needed)

    output_filename = os.path.join(output_dir_video, f'output_{time.strftime("%Y%m%d_%H%M%S")}.avi')
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_filename, fourcc, 20.0, (640, 480))

    print("Recording video based on motion detection in frames...")
    previous_frame = None
    motion_stopped_time = None
    frame_count = 0  # Track the number of frames written to the video

    # Start video capture and continuously check for motion
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame from camera.")
            break

        # Detect motion in the current frame
        motion_in_frame = detect_motion_in_frame(frame, previous_frame)
        previous_frame = frame.copy()

        if motion_in_frame:
            out.write(frame)  # Write the frame to the output file
            frame_count += 1  # Increment frame count
            motion_stopped_time = None  # Reset motion stopped timer
            last_motion_time = time.time()  # Update last motion time
        else:
            # If motion stops, start the timer
            if motion_stopped_time is None:
                motion_stopped_time = time.time()
            elif time.time() - motion_stopped_time >= 5:  # Wait 5 seconds with no motion
                print("No motion detected for 5 seconds. Stopping recording...")
                break

    cap.release()
    out.release()
    print("Video recording ended.")

    # Calculate video duration in seconds
    video_duration = frame_count / 20.0  # FPS is 20.0, as set when writing the video
    print(f"Video duration: {video_duration:.2f} seconds.")

    if os.path.exists(output_filename):
        upload_video_to_firebase(output_filename)
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
    return (frame_normalized * 255).astype('uint8')

# Function to ask for continuous mode
def ask_continuous_mode():
    """Ask the user if they want to enable continuous mode. If 'no', the script stops."""
    global continuous_mode
    while True:
        response = input("Do you want to enter continuous mode? (yes/no): ").strip().lower()
        if response == 'yes':
            continuous_mode = True
            print("Continuous mode enabled.")
            return True
        elif response == 'no':
            continuous_mode = False
            print("Continuous mode disabled. Exiting motion detection.")
            os._exit(0)  # Use os._exit(0) to exit immediately and return to the terminal
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

# PIR sensor event handling
def motion_function():
    global continuous_mode
    if not motion_detected or continuous_mode:  # Check motion detection or if in continuous mode
        data = {
            'motion': 'detected',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        ref.push(data)
        print("Motion detected and data pushed to Firebase")

        # Run the full process
        initial_capture()
        capture_video()

        if not continuous_mode:  # Ask about continuous mode if not already enabled
            ask_continuous_mode()

def no_motion_function():
    data = {
        'motion': 'stopped',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    ref.push(data)
    print("Motion stopped and data pushed to Firebase")

# PIR sensor event handlers
pir.when_motion = motion_function
pir.when_no_motion = no_motion_function

# Start the script
print("Waiting for motion...")
pause()
