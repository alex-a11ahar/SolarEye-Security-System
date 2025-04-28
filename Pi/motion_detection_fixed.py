import cv2
import os
import time
import firebase_admin
from firebase_admin import credentials, db, storage
from gpiozero import MotionSensor
import sys  # For exiting the script

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
capture_duration = 10  # Default duration for video capture (seconds)
running = True  # Flag to control the main loop

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

def capture_video():
    """Captures video for a fixed user-specified duration."""
    global motion_detected
    motion_detected = True  # Set motion_detected to True when video capture starts

    # Video capture from USB camera
    camera_index = 0
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    output_filename = os.path.join(output_dir_video, f'output_{time.strftime("%Y%m%d_%H%M%S")}.avi')
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_filename, fourcc, 20.0, (640, 480))

    print(f"Recording video for {capture_duration} seconds...")
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame from camera.")
            break

        out.write(frame)  # Write the frame to the output file

        if time.time() - start_time >= capture_duration:
            print(f"Recording complete. Captured video for {capture_duration} seconds.")
            break

    cap.release()
    out.release()
    print("Video recording ended.")

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

def ask_continuous_mode():
    """Ask the user if they want to enable continuous mode."""
    global continuous_mode, running
    while True:
        response = input("Do you want to enter continuous mode? (yes/no): ").strip().lower()
        if response == 'yes':
            continuous_mode = True
            print("Continuous mode enabled.")
            return True
        elif response == 'no':
            print("Continuous mode disabled. Exiting program.")
            running = False  # Set running flag to False
            sys.exit(0)  # Exit the program and return to the terminal
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

# Functions to handle motion events and push data to Firebase
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

# Main execution
print("Enter the desired video capture duration in seconds:")
while True:
    try:
        capture_duration = int(input("Duration: ").strip())
        if capture_duration > 0:
            break
        print("Please enter a positive integer.")
    except ValueError:
        print("Invalid input. Please enter a valid number.")

pir.when_motion = motion_function
pir.when_no_motion = no_motion_function

print("Monitoring GPIO pin for sensor activation...")

# Main program loop to monitor the motion sensor and allow clean exit
try:
    while running:  # Keep running until continuous mode is disabled
        time.sleep(3)  # Sleep for 3 seconds instead of pausing
except KeyboardInterrupt:
    print("Program interrupted. Exiting.")
    sys.exit(0)  # Ensure exit back to terminal
