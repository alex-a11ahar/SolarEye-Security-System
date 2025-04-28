import cv2
import os

# Define directories
video_dir = 'videos'  # Folder containing the .avi files
output_dir = 'extracted_frames'  # Directory to save extracted frames
output_dir_preprocessed = 'preprocessed_frames'  # Directory to save preprocessed frames

# Function to get the latest .avi file
def get_latest_video_file(video_dir):
    avi_files = [f for f in os.listdir(video_dir) if f.endswith('.avi')]
    if not avi_files:
        print("No .avi files found in the directory.")
        return None
    
    latest_file = max(
        (os.path.join(video_dir, f) for f in avi_files),
        key=os.path.getmtime
    )
    return latest_file

# Get the latest video file
video_path = get_latest_video_file(video_dir)
if not video_path:
    exit()  # Exit if no video file is found

# Create the output directory for extracted frames if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Initialize video capture
cap = cv2.VideoCapture(video_path)

frame_count = 0  # Frame counter

# Loop through the video frames and extract them
while True:
    ret, frame = cap.read()  # Read a frame
    if not ret:
        break  # Exit loop if no frame is returned

    # Save the frame as an image file
    frame_filename = os.path.join(output_dir, f'frame_{frame_count:04d}.jpg')
    cv2.imwrite(frame_filename, frame)  # Save the frame as a JPEG file
    frame_count += 1  # Increment the frame counter

# Release the video capture object
cap.release()
print(f'Extracted {frame_count} frames to the directory: {output_dir}')

# Create the output directory for preprocessed frames if it doesn't exist
if not os.path.exists(output_dir_preprocessed):
    os.makedirs(output_dir_preprocessed)

# Loop through the extracted frames and preprocess them
for frame_filename in os.listdir(output_dir):
    if frame_filename.endswith('.jpg'):
        # Read the frame
        frame_path = os.path.join(output_dir, frame_filename)
        frame = cv2.imread(frame_path)

        # Resize the frame to a fixed size (e.g., 640x480)
        frame_resized = cv2.resize(frame, (640, 480))

        # Convert the frame to grayscale
        frame_gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)

        # Normalize pixel values (optional)
        frame_normalized = frame_gray / 255.0  # Scale pixel values to [0, 1]

        # Save the preprocessed frame
        preprocessed_filename = os.path.join(output_dir_preprocessed, frame_filename)
        cv2.imwrite(preprocessed_filename, frame_normalized * 255)  # Convert back to uint8 for saving

print(f'Preprocessed frames saved to the directory: {output_dir_preprocessed}')
